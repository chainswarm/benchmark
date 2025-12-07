from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params
from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.tournament_manager import TournamentManager
from packages.benchmark.models.epoch import EpochStatus
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.tournament import (
    ParticipantStatus,
    Tournament,
    TournamentStatus,
)
from packages.jobs.base import TournamentTaskContext
from packages.jobs.celery_app import celery_app
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.tournament_repository import TournamentRepository


class TournamentOrchestratorTask(BaseTask, Singleton):
    """
    Main orchestrator that manages tournament lifecycle.
    
    Checks tournaments in each status and takes appropriate action:
    - draft → registration: When registration_start date is reached
    - registration → in_progress: When registration_end date is passed
    - in_progress → scoring: When all epoch days are complete
    - scoring → completed: When scoring is done
    """

    def execute_task(self, context: TournamentTaskContext):
        image_type = ImageType(context.image_type)
        current_date = date.fromisoformat(context.test_date) if context.test_date else date.today()
        
        logger.info("Starting tournament orchestrator", extra={
            "image_type": image_type.value,
            "current_date": str(current_date),
            "tournament_id": context.tournament_id
        })
        
        connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
        client_factory = ClientFactory(connection_params)
        
        with client_factory.client_context() as client:
            tournament_repo = TournamentRepository(client)
            tournament_manager = TournamentManager()
            
            # If specific tournament_id provided, process only that tournament
            if context.tournament_id:
                tournament = tournament_repo.get_tournament_by_id(UUID(context.tournament_id))
                if tournament:
                    self._process_tournament(
                        tournament=tournament,
                        current_date=current_date,
                        tournament_repo=tournament_repo,
                        tournament_manager=tournament_manager
                    )
                    return {
                        "status": "success",
                        "tournament_id": context.tournament_id,
                        "tournament_status": tournament.status.value
                    }
                else:
                    logger.warning("Tournament not found", extra={"tournament_id": context.tournament_id})
                    return {"status": "not_found", "tournament_id": context.tournament_id}
            
            # Process all tournaments for this image type
            tournaments_processed = 0
            
            # Process draft tournaments
            draft_tournaments = tournament_repo.get_tournaments_by_status(TournamentStatus.DRAFT)
            for tournament in draft_tournaments:
                if tournament.image_type == image_type:
                    self._process_draft(tournament, current_date, tournament_repo)
                    tournaments_processed += 1
            
            # Process registration tournaments
            registration_tournaments = tournament_repo.get_tournaments_by_status(TournamentStatus.REGISTRATION)
            for tournament in registration_tournaments:
                if tournament.image_type == image_type:
                    self._process_registration_phase(tournament, current_date, tournament_repo, tournament_manager)
                    tournaments_processed += 1
            
            # Process in_progress tournaments
            in_progress_tournaments = tournament_repo.get_tournaments_by_status(TournamentStatus.IN_PROGRESS)
            for tournament in in_progress_tournaments:
                if tournament.image_type == image_type:
                    self._process_in_progress(tournament, current_date, tournament_repo, tournament_manager)
                    tournaments_processed += 1
            
            # Process scoring tournaments
            scoring_tournaments = tournament_repo.get_tournaments_by_status(TournamentStatus.SCORING)
            for tournament in scoring_tournaments:
                if tournament.image_type == image_type:
                    self._process_scoring(tournament, tournament_repo)
                    tournaments_processed += 1
            
            logger.info("Tournament orchestrator completed", extra={
                "image_type": image_type.value,
                "tournaments_processed": tournaments_processed
            })
            
            return {
                "status": "success",
                "image_type": image_type.value,
                "tournaments_processed": tournaments_processed
            }

    def _process_tournament(
        self,
        tournament: Tournament,
        current_date: date,
        tournament_repo: TournamentRepository,
        tournament_manager: TournamentManager
    ):
        """Process a single tournament based on its status."""
        logger.info("Processing tournament", extra={
            "tournament_id": str(tournament.tournament_id),
            "status": tournament.status.value,
            "current_date": str(current_date)
        })
        
        if tournament.status == TournamentStatus.DRAFT:
            self._process_draft(tournament, current_date, tournament_repo)
        elif tournament.status == TournamentStatus.REGISTRATION:
            self._process_registration_phase(tournament, current_date, tournament_repo, tournament_manager)
        elif tournament.status == TournamentStatus.IN_PROGRESS:
            self._process_in_progress(tournament, current_date, tournament_repo, tournament_manager)
        elif tournament.status == TournamentStatus.SCORING:
            self._process_scoring(tournament, tournament_repo)

    def _process_draft(
        self,
        tournament: Tournament,
        current_date: date,
        tournament_repo: TournamentRepository
    ):
        """Move tournament from draft to registration when registration start date is reached."""
        if current_date >= tournament.registration_start:
            logger.info("Moving tournament to registration", extra={
                "tournament_id": str(tournament.tournament_id),
                "registration_start": str(tournament.registration_start)
            })
            tournament_repo.update_tournament_status(
                tournament.tournament_id,
                TournamentStatus.REGISTRATION
            )

    def _process_registration_phase(
        self,
        tournament: Tournament,
        current_date: date,
        tournament_repo: TournamentRepository,
        tournament_manager: TournamentManager
    ):
        """Handle registration period - move to in_progress when registration ends."""
        if current_date > tournament.registration_end:
            logger.info("Registration period ended, starting competition", extra={
                "tournament_id": str(tournament.tournament_id),
                "registration_end": str(tournament.registration_end),
                "competition_start": str(tournament.competition_start)
            })
            
            # Create tournament epoch if not exists
            epoch = tournament_repo.get_tournament_epoch(tournament.tournament_id)
            if not epoch:
                epoch = tournament_manager.create_tournament_epoch(tournament)
                tournament_repo.insert_epoch(epoch)
            
            tournament_repo.update_epoch_status(epoch.epoch_id, EpochStatus.RUNNING)
            
            # Update all participants to active
            participants = tournament_repo.get_participants(tournament.tournament_id)
            for participant in participants:
                tournament_repo.update_participant_status(
                    tournament.tournament_id,
                    participant.hotkey,
                    ParticipantStatus.ACTIVE
                )
            
            # Move tournament to in_progress
            tournament_repo.update_tournament_status(
                tournament.tournament_id,
                TournamentStatus.IN_PROGRESS,
                current_day=1
            )

    def _process_in_progress(
        self,
        tournament: Tournament,
        current_date: date,
        tournament_repo: TournamentRepository,
        tournament_manager: TournamentManager
    ):
        """Execute daily tests - trigger day execution tasks."""
        # Calculate current day number
        days_elapsed = (current_date - tournament.competition_start).days + 1
        
        logger.info("Processing in_progress tournament", extra={
            "tournament_id": str(tournament.tournament_id),
            "current_date": str(current_date),
            "days_elapsed": days_elapsed,
            "epoch_days": tournament.epoch_days
        })
        
        # Check if tournament is complete
        if current_date > tournament.competition_end:
            logger.info("Tournament competition ended, moving to scoring", extra={
                "tournament_id": str(tournament.tournament_id),
                "competition_end": str(tournament.competition_end)
            })
            
            # Update epoch to completed
            epoch = tournament_repo.get_tournament_epoch(tournament.tournament_id)
            if epoch:
                tournament_repo.update_epoch_status(epoch.epoch_id, EpochStatus.COMPLETED)
            
            # Move to scoring phase
            tournament_repo.update_tournament_status(
                tournament.tournament_id,
                TournamentStatus.SCORING
            )
            
            # Trigger scoring task
            self._trigger_scoring_task(tournament)
            return
        
        # Check if we need to run today's tests
        runs_today = tournament_repo.get_daily_runs_for_tournament(tournament.tournament_id, current_date)
        
        if not runs_today:
            logger.info("Triggering day execution for tournament", extra={
                "tournament_id": str(tournament.tournament_id),
                "test_date": str(current_date),
                "day_number": days_elapsed
            })
            
            # Update current day
            tournament_repo.update_tournament_status(
                tournament.tournament_id,
                TournamentStatus.IN_PROGRESS,
                current_day=days_elapsed
            )
            
            # Trigger day execution task
            self._trigger_day_execution_task(tournament, current_date)
        else:
            logger.info("Day execution already started", extra={
                "tournament_id": str(tournament.tournament_id),
                "runs_count": len(runs_today)
            })

    def _process_scoring(
        self,
        tournament: Tournament,
        tournament_repo: TournamentRepository
    ):
        """Calculate final scores and determine winner."""
        logger.info("Processing scoring for tournament", extra={
            "tournament_id": str(tournament.tournament_id)
        })
        
        # Check if results already exist
        results = tournament_repo.get_results(tournament.tournament_id)
        
        if not results:
            # Trigger scoring task if not already running
            self._trigger_scoring_task(tournament)
        else:
            # Results exist - check if tournament should be completed
            winner = next((r for r in results if r.is_winner), None)
            if winner:
                logger.info("Tournament scoring complete", extra={
                    "tournament_id": str(tournament.tournament_id),
                    "winner_hotkey": winner.hotkey,
                    "beat_baseline": winner.beat_baseline
                })
                
                # Complete the tournament
                tournament_repo.complete_tournament(
                    tournament.tournament_id,
                    winner.hotkey,
                    winner.beat_baseline
                )
                
                # If winner beat baseline, trigger baseline promotion
                if winner.beat_baseline:
                    self._trigger_baseline_promotion_task(tournament, winner.hotkey)

    def _trigger_day_execution_task(self, tournament: Tournament, test_date: date):
        """Trigger the tournament day execution task."""
        from packages.jobs.tasks.tournament_day_execution_task import tournament_day_execution_task
        
        tournament_day_execution_task.delay(
            tournament_id=str(tournament.tournament_id),
            image_type=tournament.image_type.value,
            test_date=str(test_date)
        )

    def _trigger_scoring_task(self, tournament: Tournament):
        """Trigger the tournament scoring task."""
        from packages.jobs.tasks.tournament_scoring_task import tournament_scoring_task
        
        tournament_scoring_task.delay(
            tournament_id=str(tournament.tournament_id),
            image_type=tournament.image_type.value
        )

    def _trigger_baseline_promotion_task(self, tournament: Tournament, winner_hotkey: str):
        """Trigger the baseline promotion task."""
        from packages.jobs.tasks.baseline_promotion_task import baseline_promotion_task
        
        baseline_promotion_task.delay(
            tournament_id=str(tournament.tournament_id),
            image_type=tournament.image_type.value,
            winner_hotkey=winner_hotkey
        )


@celery_app.task(
    bind=True,
    base=TournamentOrchestratorTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 300
    },
    time_limit=7200,
    soft_time_limit=7000
)
def tournament_orchestrator_task(
    self,
    image_type: str,
    tournament_id: str = None,
    test_date: str = None
):
    context = TournamentTaskContext(
        tournament_id=tournament_id,
        image_type=image_type,
        test_date=test_date or str(date.today())
    )
    
    return self.run(context)