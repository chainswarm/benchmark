from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ImageType(str, Enum):
    ANALYTICS = 'analytics'
    ML = 'ml'


class MinerStatus(str, Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    DISABLED = 'disabled'
    FAILED = 'failed'


@dataclass
class Miner:
    hotkey: str
    image_type: ImageType
    github_repository: str
    registered_at: datetime
    last_updated_at: datetime
    status: MinerStatus
    validation_error: Optional[str] = None

    @property
    def database_name(self) -> str:
        return f"{self.image_type.value}_{self.hotkey}"

    @property
    def docker_image_tag(self) -> str:
        return f"{self.image_type.value}_{self.hotkey}"


@dataclass
class MinerDatabase:
    hotkey: str
    image_type: ImageType
    database_name: str
    created_at: datetime
    last_used_at: datetime
    status: str