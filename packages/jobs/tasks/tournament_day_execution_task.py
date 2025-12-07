from datetime import date, datetime
from typing import List
from uuid import UUID, uuid4

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params
from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.managers.tournament_manager import TournamentManager
from packages.benchmark.managers.validation_manager import ValidationManager
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import AnalyticsDailyRun, RunStatus
from packages.benchmark.models.tournament import (
    ParticipantStatus,
    TournamentParticipant,
)
from packages.jobs.base import TournamentTaskContext
from packages.jobs.celery_app import celery_app
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.tournament_repository import TournamentRepository
from packages.storage.repositories.benchmark_results_repository import BenchmarkResultsRepository


class TournamentDayExecutionTask(BaseTask, Singleton):
    """
    Executes daily benchmarking for all participants sequentially.
    
    Execution flow:
    1. Get participants ordered by registration_order
    2. Run baseline first (order=0)
    3. Then run each miner in order
    4. For each participant:
       - For each network in test_networks
       - For each window in test_window_days
       - Run container and record results
    """

    def execute_task(self, context: TournamentTaskContext):
        tournament_id = UUID(context.tournament_id)
        image_type = ImageType(context.image_type)
        test_date = date.fromisoformat(context.test_date)
        
        logger.info("Starting tournament day execution", extra={
            "tournament_id": str(tournament_id),
            "image_type": image_type.value,
            "test_date": str(test_date)
        })
        
        connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
        client_factory = ClientFactory(connection_params)
        
        with client_factory.client_context() as client:
            tournament_repo = TournamentRepository(client)
            tournament_manager = TournamentManager()
            docker_manager = DockerManager()
            dataset_manager = DatasetManager()
            validation_manager = ValidationManager()
            
            # Get tournament details
            tournament = tournament_repo.get_tournament_by_id(tournament_id)
            if not tournament:
                raise ValueError(f"Tournament not found: {tournament_id}")
            
            # Get epoch for this tournament
            epoch = tournament_repo.get_tournament_epoch(tournament_id)
            if not epoch:
                raise ValueError(f"Tournament epoch not found: {tournament_id}")
            
            # Get participants ordered by registration_order
            participants = tournament_repo.get_participants(tournament_id)
            execution_queue = tournament_manager.get_execution_queue(participants)
            
            logger.info("Executing tournament day", extra={
                "tournament_id": str(tournament_id),
                "test_date": str(test_date),
                "participants_count": len(execution_queue),
                "networks": tournament.test_networks,
                "window_days": tournament.test_window_days
            })
            
            run_order = 0
            results_summary = {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "timeout_runs": 0
            }
            
            # Process each participant in order
            for participant in execution_queue:
                if participant.status not in [ParticipantStatus.ACTIVE, ParticipantStatus.REGISTERED]:
                    logger.info("Skipping inactive participant", extra={
                        "hotkey": participant.hotkey,
                        "status": participant.status.value
                    })
                    continue
                
                # For each network/window combination
                for network in tournament.test_networks:
                    for window_days in tournament.test_window_days:
                        run_order += 1
                        
                        try:
                            run_result = self._execute_participant_run(
                                tournament=tournament,
                                epoch_id=epoch.epoch_id,
                                participant=participant,
                                test_date=test_date,
                                network=network,
                                window_days=window_days,
                                run_order=run_order,
                                tournament_repo=tournament_repo,
                                docker_manager=docker_manager,
                                dataset_manager=dataset_manager,
                                validation_manager=validation_manager,
                                image_type=image_type
                            )
                            
                            results_summary["total_runs"] += 1
                            if run_result["status"] == "success":
                                results_summary["successful_runs"] += 1
                            elif run_result["status"] == "timeout":
                                results_summary["timeout_runs"] += 1
                            else:
                                results_summary["failed_runs"] += 1
                                
                        except Exception as e:
                            logger.error("Failed to execute participant run", extra={
                                "tournament_id": str(tournament_id),
                                "hotkey": participant.hotkey,
                                "network": network,
                                "window_days": window_days,
                                "error": str(e)
                            })
                            results_summary["total_runs"] += 1
                            results_summary["failed_runs"] += 1
            
            logger.info("Tournament day execution completed", extra={
                "tournament_id": str(tournament_id),
                "test_date": str(test_date),
                **results_summary
            })
            
            return {
                "status": "success",
                "tournament_id": str(tournament_id),
                "test_date": str(test_date),
                **results_summary
            }

    def _execute_participant_run(
        self,
        tournament,
        epoch_id: UUID,
        participant: TournamentParticipant,
        test_date: date,
        network: str,
        window_days: int,
        run_order: int,
        tournament_repo: TournamentRepository,
        docker_manager: DockerManager,
        dataset_manager: DatasetManager,
        validation_manager: ValidationManager,
        image_type: ImageType
    ) -> dict:
        """Execute a single run for a participant with a specific network/window configuration."""
        run_id = uuid4()
        started_at = datetime.now()
        
        logger.info("Executing participant run", extra={
            "tournament_id": str(tournament.tournament_id),
            "hotkey": participant.hotkey,
            "run_id": str(run_id),
            "network": network,
            "window_days": window_days,
            "run_order": run_order
        })
        
        run = AnalyticsDailyRun(
            run_id=run_id,
            epoch_id=epoch_id,
            hotkey=participant.hotkey,
            test_date=test_date,
            network=network,
            window_days=window_days,
            processing_date=test_date,
            execution_time_seconds=0.0,
            container_exit_code=0,
            gpu_memory_peak_mb=0.0,
            synthetic_patterns_expected=0,
            synthetic_patterns_found=0,
            synthetic_patterns_recall=0.0,
            novelty_patterns_reported=0,
            novelty_patterns_validated=0,
            novelty_addresses_valid=True,
            novelty_connections_valid=True,
            all_addresses_exist=True,
            all_connections_exist=True,
            data_correctness_passed=False,
            status=RunStatus.RUNNING,
            error_message=None,
            created_at=started_at,
            tournament_id=tournament.tournament_id,
            participant_type=participant.participant_type.value,
            run_order=run_order,
            is_disqualified=False,
            disqualification_reason=None
        )
        
        tournament_repo.insert_analytics_daily_run(run)
        
        try:
            # Prepare dataset for the run
            dataset_path = dataset_manager.fetch_dataset(network, str(test_date), window_days)
            mount_path = dataset_manager.prepare_miner_mount(dataset_path)
            
            # Run the container
            container_result = docker_manager.run_container(
                image_tag=participant.docker_image_tag,
                data_mount=mount_path,
                miner_database=participant.miner_database_name
            )
            
            # Handle timeout
            if container_result.timed_out:
                logger.warning("Participant run timed out", extra={
                    "tournament_id": str(tournament.tournament_id),
                    "hotkey": participant.hotkey,
                    "run_id": str(run_id),
                    "execution_time": container_result.execution_time_seconds
                })
                
                self._update_run_result(
                    tournament_repo=tournament_repo,
                    tournament_id=tournament.tournament_id,
                    run_id=run_id,
                    status=RunStatus.TIMEOUT,
                    execution_time=container_result.execution_time_seconds,
                    pattern_accuracy=0.0,
                    data_correctness_passed=False
                )
                
                return {
                    "status": "timeout",
                    "run_id": str(run_id),
                    "execution_time": container_result.execution_time_seconds
                }
            
            # Handle non-zero exit code
            if container_result.exit_code != 0:
                logger.warning("Participant run failed", extra={
                    "tournament_id": str(tournament.tournament_id),
                    "hotkey": participant.hotkey,
                    "run_id": str(run_id),
                    "exit_code": container_result.exit_code
                })
                
                self._update_run_result(
                    tournament_repo=tournament_repo,
                    tournament_id=tournament.tournament_id,
                    run_id=run_id,
                    status=RunStatus.FAILED,
                    execution_time=container_result.execution_time_seconds,
                    pattern_accuracy=0.0,
                    data_correctness_passed=False
                )
                
                return {
                    "status": "failed",
                    "run_id": str(run_id),
                    "exit_code": container_result.exit_code
                }
            
            # Validate results
            validation_result = validation_manager.validate_output(
                miner_database=participant.miner_database_name,
                network=network,
                window_days=window_days,
                image_type=image_type
            )
            
            # Calculate pattern accuracy
            pattern_accuracy = validation_result.pattern_accuracy if hasattr(validation_result, 'pattern_accuracy') else 0.0
            data_correctness_passed = validation_result.is_valid if hasattr(validation_result, 'is_valid') else False
            
            logger.info("Participant run completed successfully", extra={
                "tournament_id": str(tournament.tournament_id),
                "hotkey": participant.hotkey,
                "run_id": str(run_id),
                "execution_time": container_result.execution_time_seconds,
                "pattern_accuracy": pattern_accuracy,
                "data_correctness_passed": data_correctness_passed
            })
            
            self._update_run_result(
                tournament_repo=tournament_repo,
                tournament_id=tournament.tournament_id,
                run_id=run_id,
                status=RunStatus.COMPLETED,
                execution_time=container_result.execution_time_seconds,
                pattern_accuracy=pattern_accuracy,
                data_correctness_passed=data_correctness_passed
            )
            
            # Also record to standard benchmark tables for consistency
            self._record_to_benchmark_tables(
                participant=participant,
                tournament=tournament,
                test_date=test_date,
                network=network,
                window_days=window_days,
                execution_time=container_result.execution_time_seconds,
                pattern_accuracy=pattern_accuracy,
                image_type=image_type
            )
            
            return {
                "status": "success",
                "run_id": str(run_id),
                "execution_time": container_result.execution_time_seconds,
                "pattern_accuracy": pattern_accuracy
            }
            
        except Exception as e:
            logger.error("Participant run execution error", extra={
                "tournament_id": str(tournament.tournament_id),
                "hotkey": participant.hotkey,
                "run_id": str(run_id),
                "error": str(e)
            })
            
            self._update_run_result(
                tournament_repo=tournament_repo,
                tournament_id=tournament.tournament_id,
                run_id=run_id,
                status=RunStatus.FAILED,
                execution_time=0.0,
                pattern_accuracy=0.0,
                data_correctness_passed=False
            )
            
            raise

    def _update_run_result(
        self,
        tournament_repo: TournamentRepository,
        tournament_id: UUID,
        run_id: UUID,
        status: RunStatus,
        execution_time: float,
        pattern_accuracy: float,
        data_correctness_passed: bool
    ):
        tournament_repo.update_analytics_daily_run_status(
            run_id=run_id,
            status=status
        )

    def _record_to_benchmark_tables(
        self,
        participant: TournamentParticipant,
        tournament,
        test_date: date,
        network: str,
        window_days: int,
        execution_time: float,
        pattern_accuracy: float,
        image_type: ImageType
    ):
        """
        Record tournament runs to standard benchmark tables for data consistency.
        This allows tournament data to be included in overall analytics.
        """
        # This is a placeholder for recording to benchmark_*_daily_runs tables
        # The actual implementation depends on the BenchmarkResultsRepository structure
        logger.debug("Recording to benchmark tables", extra={
            "hotkey": participant.hotkey,
            "network": network,
            "window_days": window_days,
            "image_type": image_type.value
        })


@celery_app.task(
    bind=True,
    base=TournamentDayExecutionTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=14400,  # 4 hours - tournaments have multiple participants
    soft_time_limit=14000
)
def tournament_day_execution_task(
    self,
    tournament_id: str,
    image_type: str,
    test_date: str
):
    context = TournamentTaskContext(
        tournament_id=tournament_id,
        image_type=image_type,
        test_date=test_date
    )
    
    return self.run(context)