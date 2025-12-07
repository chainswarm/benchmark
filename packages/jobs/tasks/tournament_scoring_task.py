from datetime import datetime
from statistics import mean
from typing import List
from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params
from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.tournament_manager import TournamentManager
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import AnalyticsDailyRun, RunStatus
from packages.benchmark.models.tournament import (
    ParticipantStatus,
    ParticipantType,
    TournamentParticipant,
    TournamentResult,
    TournamentStatus,
)
from packages.jobs.base import TournamentTaskContext
from packages.jobs.celery_app import celery_app
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.tournament_repository import TournamentRepository


class TournamentScoringTask(BaseTask, Singleton):
    """
    Calculates final scores after all tournament days are complete.
    
    Scoring flow:
    1. Aggregate all daily runs per participant
    2. Calculate scores using TournamentManager.calculate_participant_score()
    3. Determine rankings using TournamentManager.determine_rankings()
    4. Insert results to tournament_results
    5. Update tournament with winner info
    """

    def execute_task(self, context: TournamentTaskContext):
        tournament_id = UUID(context.tournament_id)
        image_type = ImageType(context.image_type)
        
        logger.info("Starting tournament scoring", extra={
            "tournament_id": str(tournament_id),
            "image_type": image_type.value
        })
        
        connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
        client_factory = ClientFactory(connection_params)
        
        with client_factory.client_context() as client:
            tournament_repo = TournamentRepository(client)
            tournament_manager = TournamentManager()
            
            # Get tournament details
            tournament = tournament_repo.get_tournament_by_id(tournament_id)
            if not tournament:
                raise ValueError(f"Tournament not found: {tournament_id}")
            
            # Get all participants
            participants = tournament_repo.get_participants(tournament_id)
            
            logger.info("Calculating scores for tournament participants", extra={
                "tournament_id": str(tournament_id),
                "participants_count": len(participants)
            })
            
            # Get baseline participant and calculate baseline average time
            baseline_participant = next(
                (p for p in participants if p.participant_type == ParticipantType.BASELINE),
                None
            )
            
            baseline_avg_time = 0.0
            if baseline_participant:
                baseline_runs = tournament_repo.get_participant_runs(
                    tournament_id,
                    baseline_participant.hotkey
                )
                completed_baseline_runs = [
                    r for r in baseline_runs
                    if r.status == RunStatus.COMPLETED
                ]
                if completed_baseline_runs:
                    baseline_avg_time = mean([r.execution_time_seconds for r in completed_baseline_runs])
            
            logger.info("Baseline average execution time", extra={
                "tournament_id": str(tournament_id),
                "baseline_avg_time": baseline_avg_time
            })
            
            # Calculate scores for each participant
            results: List[TournamentResult] = []
            
            for participant in participants:
                # Get all runs for this participant
                participant_runs = tournament_repo.get_participant_runs(
                    tournament_id,
                    participant.hotkey
                )
                
                completed_runs = [
                    r for r in participant_runs
                    if r.status == RunStatus.COMPLETED
                ]
                
                logger.info("Calculating participant score", extra={
                    "tournament_id": str(tournament_id),
                    "hotkey": participant.hotkey,
                    "total_runs": len(participant_runs),
                    "completed_runs": len(completed_runs)
                })
                
                # Handle participants with no completed runs
                if not completed_runs:
                    result = self._create_disqualified_result(
                        tournament_id=tournament_id,
                        participant=participant,
                        reason="no_completed_runs"
                    )
                else:
                    # Calculate score using tournament manager
                    result = tournament_manager.calculate_participant_score(
                        tournament_id=tournament_id,
                        participant=participant,
                        runs=completed_runs,
                        baseline_avg_time=baseline_avg_time
                    )
                
                results.append(result)
            
            # Determine rankings
            ranked_results = tournament_manager.determine_rankings(results)
            
            # Insert results
            for result in ranked_results:
                tournament_repo.insert_result(result)
                
                # Update participant status
                if result.final_score > 0:
                    tournament_repo.update_participant_status(
                        tournament_id,
                        result.hotkey,
                        ParticipantStatus.COMPLETED
                    )
                else:
                    tournament_repo.update_participant_status(
                        tournament_id,
                        result.hotkey,
                        ParticipantStatus.DISQUALIFIED
                    )
            
            # Find winner and baseline results
            winner = next((r for r in ranked_results if r.is_winner), None)
            baseline_result = next(
                (r for r in ranked_results if r.participant_type == ParticipantType.BASELINE),
                None
            )
            
            if winner:
                winner_beat_baseline = winner.beat_baseline
                
                logger.info("Tournament scoring completed", extra={
                    "tournament_id": str(tournament_id),
                    "winner_hotkey": winner.hotkey,
                    "winner_score": winner.final_score,
                    "baseline_score": baseline_result.final_score if baseline_result else 0.0,
                    "winner_beat_baseline": winner_beat_baseline,
                    "total_participants": len(ranked_results)
                })
                
                # Complete the tournament
                tournament_repo.complete_tournament(
                    tournament_id=tournament_id,
                    winner_hotkey=winner.hotkey,
                    baseline_beaten=winner_beat_baseline
                )
                
                return {
                    "status": "success",
                    "tournament_id": str(tournament_id),
                    "winner_hotkey": winner.hotkey,
                    "winner_score": winner.final_score,
                    "winner_beat_baseline": winner_beat_baseline,
                    "participants_scored": len(ranked_results)
                }
            else:
                logger.warning("No winner determined for tournament", extra={
                    "tournament_id": str(tournament_id)
                })
                
                return {
                    "status": "no_winner",
                    "tournament_id": str(tournament_id),
                    "participants_scored": len(ranked_results)
                }

    def _create_disqualified_result(
        self,
        tournament_id: UUID,
        participant: TournamentParticipant,
        reason: str
    ) -> TournamentResult:
        """Create a zero-score result for a disqualified participant."""
        logger.warning("Participant disqualified", extra={
            "tournament_id": str(tournament_id),
            "hotkey": participant.hotkey,
            "reason": reason
        })
        
        return TournamentResult(
            tournament_id=tournament_id,
            hotkey=participant.hotkey,
            participant_type=participant.participant_type,
            pattern_accuracy_score=0.0,
            data_correctness_score=0.0,
            performance_score=0.0,
            final_score=0.0,
            data_correctness_all_days=False,
            all_runs_within_time_limit=False,
            days_completed=0,
            total_runs_completed=0,
            average_execution_time_seconds=0.0,
            baseline_comparison_ratio=0.0,
            rank=0,
            is_winner=False,
            beat_baseline=False,
            miners_beaten=0,
            calculated_at=datetime.now()
        )


@celery_app.task(
    bind=True,
    base=TournamentScoringTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=1800,  # 30 minutes for scoring
    soft_time_limit=1700
)
def tournament_scoring_task(
    self,
    tournament_id: str,
    image_type: str
):
    context = TournamentTaskContext(
        tournament_id=tournament_id,
        image_type=image_type,
        test_date=None
    )
    
    return self.run(context)