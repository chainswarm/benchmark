from dataclasses import dataclass
from typing import Optional

from chainswarm_core.jobs import BaseTaskContext as CoreBaseTaskContext, BaseTaskResult


@dataclass
class BenchmarkTaskContext(CoreBaseTaskContext):
    """Extended task context with benchmark-specific fields."""
    hotkey: Optional[str] = None
    image_type: Optional[str] = None
    epoch_id: Optional[str] = None
    github_repository: Optional[str] = None
    docker_image_tag: Optional[str] = None
    miner_database_name: Optional[str] = None


__all__ = ["BenchmarkTaskContext", "BaseTaskResult"]