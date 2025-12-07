from dataclasses import dataclass
from typing import Optional

from chainswarm_core.jobs import BaseTaskContext as CoreBaseTaskContext, BaseTaskResult


@dataclass
class BenchmarkTaskContext(CoreBaseTaskContext):
    """Extended task context with benchmark-specific fields.
    
    Field Naming Convention:
    - `image_tag` / `miner_database`: Runtime references passed between tasks
    - `docker_image_tag` / `miner_database_name`: Persisted field names in epoch/result models
    
    The duplication exists for compatibility with different contexts (task passing vs database persistence).
    """
    hotkey: Optional[str] = None
    image_type: Optional[str] = None
    epoch_id: Optional[str] = None
    run_id: Optional[str] = None
    github_repository: Optional[str] = None
    docker_image_tag: Optional[str] = None
    image_tag: Optional[str] = None
    miner_database_name: Optional[str] = None
    miner_database: Optional[str] = None
    repository_path: Optional[str] = None
    data_mount_path: Optional[str] = None
    test_date: Optional[str] = None
    timeout: Optional[int] = None


@dataclass
class TournamentTaskContext(CoreBaseTaskContext):
    """Task context for tournament-related tasks.
    
    Used by:
    - tournament_orchestrator_task: Manages tournament lifecycle
    - tournament_day_execution_task: Executes daily benchmarks for all participants
    - tournament_scoring_task: Calculates final scores and rankings
    - baseline_promotion_task: Promotes winner as new baseline
    """
    tournament_id: Optional[str] = None
    image_type: Optional[str] = None
    test_date: Optional[str] = None
    winner_hotkey: Optional[str] = None
    epoch_id: Optional[str] = None


__all__ = ["BenchmarkTaskContext", "TournamentTaskContext", "BaseTaskResult"]