from datetime import datetime
from typing import Optional
from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params
from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.baseline_manager import BaselineManager
from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.models.baseline import BaselineStatus
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.tournament import ParticipantType
from packages.jobs.base import TournamentTaskContext
from packages.jobs.celery_app import celery_app
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.baseline_repository import BaselineRepository
from packages.storage.repositories.tournament_repository import TournamentRepository


class BaselinePromotionTask(BaseTask, Singleton):
    """
    Promotes the tournament winner as the new baseline.
    
    Promotion flow:
    1. Check if winner beat baseline
    2. Fork winner's repository using BaselineManager.fork_winner_as_baseline()
    3. Build new baseline image
    4. Update baseline_registry
    5. Deprecate old baseline
    """

    def execute_task(self, context: TournamentTaskContext):
        tournament_id = UUID(context.tournament_id)
        image_type = ImageType(context.image_type)
        winner_hotkey = context.winner_hotkey
        
        logger.info("Starting baseline promotion", extra={
            "tournament_id": str(tournament_id),
            "image_type": image_type.value,
            "winner_hotkey": winner_hotkey
        })
        
        connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
        client_factory = ClientFactory(connection_params)
        
        with client_factory.client_context() as client:
            tournament_repo = TournamentRepository(client)
            baseline_repo = BaselineRepository(client)
            baseline_manager = BaselineManager()
            docker_manager = DockerManager()
            
            # Get tournament details
            tournament = tournament_repo.get_tournament_by_id(tournament_id)
            if not tournament:
                raise ValueError(f"Tournament not found: {tournament_id}")
            
            # Verify winner beat baseline
            if not tournament.baseline_beaten:
                logger.info("Winner did not beat baseline, skipping promotion", extra={
                    "tournament_id": str(tournament_id),
                    "winner_hotkey": winner_hotkey
                })
                return {
                    "status": "skipped",
                    "reason": "winner_did_not_beat_baseline",
                    "tournament_id": str(tournament_id)
                }
            
            # Get winner participant details
            winner_participant = tournament_repo.get_participant(tournament_id, winner_hotkey)
            if not winner_participant:
                raise ValueError(f"Winner participant not found: {winner_hotkey}")
            
            if winner_participant.participant_type == ParticipantType.BASELINE:
                logger.info("Winner is baseline, skipping promotion", extra={
                    "tournament_id": str(tournament_id)
                })
                return {
                    "status": "skipped",
                    "reason": "winner_is_baseline",
                    "tournament_id": str(tournament_id)
                }
            
            # Get current active baseline
            current_baseline = baseline_repo.get_active_baseline(image_type)
            current_version = current_baseline.version if current_baseline else None
            
            logger.info("Forking winner as new baseline", extra={
                "tournament_id": str(tournament_id),
                "winner_hotkey": winner_hotkey,
                "winner_repo": winner_participant.github_repository,
                "current_version": current_version
            })
            
            # Get the winner's commit hash from their docker image tag
            # The commit hash would typically be stored during registration
            # For now, we'll extract it or use a placeholder
            winner_commit_hash = self._get_winner_commit_hash(winner_participant)
            
            try:
                # Fork winner's repository as new baseline
                new_baseline = baseline_manager.fork_winner_as_baseline(
                    winner_hotkey=winner_hotkey,
                    winner_repo_url=winner_participant.github_repository,
                    winner_commit_hash=winner_commit_hash,
                    image_type=image_type,
                    tournament_id=tournament_id,
                    current_version=current_version
                )
                
                # Insert new baseline record (status: BUILDING)
                baseline_repo.insert_baseline(new_baseline)
                
                logger.info("Building new baseline Docker image", extra={
                    "baseline_id": str(new_baseline.baseline_id),
                    "version": new_baseline.version
                })
                
                # Build the new baseline Docker image
                image_tag = baseline_manager.build_baseline_image(new_baseline)
                
                # Update baseline status to ACTIVE
                baseline_repo.update_baseline_status(
                    new_baseline.baseline_id,
                    BaselineStatus.ACTIVE,
                    activated_at=datetime.now()
                )
                
                # Deprecate old baseline
                if current_baseline:
                    logger.info("Deprecating old baseline", extra={
                        "old_baseline_id": str(current_baseline.baseline_id),
                        "old_version": current_baseline.version
                    })
                    
                    baseline_repo.update_baseline_status(
                        current_baseline.baseline_id,
                        BaselineStatus.DEPRECATED,
                        deprecated_at=datetime.now()
                    )
                
                logger.info("Baseline promotion completed successfully", extra={
                    "tournament_id": str(tournament_id),
                    "new_baseline_id": str(new_baseline.baseline_id),
                    "new_version": new_baseline.version,
                    "docker_image_tag": image_tag,
                    "originated_from_hotkey": winner_hotkey
                })
                
                return {
                    "status": "success",
                    "tournament_id": str(tournament_id),
                    "new_baseline_id": str(new_baseline.baseline_id),
                    "new_version": new_baseline.version,
                    "docker_image_tag": image_tag,
                    "winner_hotkey": winner_hotkey,
                    "previous_version": current_version
                }
                
            except Exception as e:
                logger.error("Failed to promote baseline", extra={
                    "tournament_id": str(tournament_id),
                    "winner_hotkey": winner_hotkey,
                    "error": str(e)
                })
                
                # If we created a baseline record, mark it as failed
                if 'new_baseline' in locals():
                    try:
                        baseline_repo.update_baseline_status(
                            new_baseline.baseline_id,
                            BaselineStatus.FAILED
                        )
                    except Exception:
                        pass
                
                raise

    def _get_winner_commit_hash(self, participant) -> str:
        """
        Extract the commit hash used for the winner's submission.
        
        This would typically be stored during tournament registration.
        For now, we attempt to extract it from the docker image tag
        or return a placeholder that will be resolved during fork.
        """
        # Docker image tag format: {image_type}_{hotkey}_{commit_short}
        # Try to extract commit from tag
        tag = participant.docker_image_tag
        parts = tag.split('_')
        
        if len(parts) >= 3:
            # Last part might be a short commit hash
            potential_hash = parts[-1]
            if len(potential_hash) >= 7 and all(c in '0123456789abcdef' for c in potential_hash.lower()):
                return potential_hash
        
        # If we can't extract, we'll need to get HEAD from the repository
        # The BaselineManager.fork_winner_as_baseline will handle this
        logger.warning("Could not extract commit hash from docker tag, will use HEAD", extra={
            "docker_image_tag": tag,
            "hotkey": participant.hotkey
        })
        
        return "HEAD"


@celery_app.task(
    bind=True,
    base=BaselinePromotionTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 120
    },
    time_limit=3600,  # 1 hour for baseline promotion (includes Docker build)
    soft_time_limit=3400
)
def baseline_promotion_task(
    self,
    tournament_id: str,
    image_type: str,
    winner_hotkey: str
):
    context = TournamentTaskContext(
        tournament_id=tournament_id,
        image_type=image_type,
        test_date=None,
        winner_hotkey=winner_hotkey
    )
    
    return self.run(context)