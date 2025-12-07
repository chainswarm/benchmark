from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from packages.benchmark.models.miner import ImageType


class BaselineStatus(Enum):
    BUILDING = 'building'
    ACTIVE = 'active'
    DEPRECATED = 'deprecated'
    FAILED = 'failed'


@dataclass
class Baseline:
    baseline_id: UUID
    image_type: ImageType
    version: str
    github_repository: str
    commit_hash: str
    docker_image_tag: str
    status: BaselineStatus
    created_at: datetime
    originated_from_tournament_id: Optional[UUID] = None
    originated_from_hotkey: Optional[str] = None
    activated_at: Optional[datetime] = None
    deprecated_at: Optional[datetime] = None