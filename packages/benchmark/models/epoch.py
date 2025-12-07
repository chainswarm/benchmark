from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from packages.benchmark.models.miner import ImageType


class EpochStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class BenchmarkEpoch:
    epoch_id: UUID
    hotkey: str
    image_type: ImageType
    start_date: date
    end_date: date
    status: EpochStatus
    docker_image_tag: str
    miner_database_name: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    tournament_id: Optional[UUID] = None  # Links epoch to a tournament

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days + 1