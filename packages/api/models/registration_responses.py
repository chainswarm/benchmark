from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RegistrationRequest(BaseModel):
    hotkey: str


class RegistrationResponse(BaseModel):
    tournament_id: UUID
    hotkey: str
    registration_order: int
    status: str
    registered_at: datetime


class ParticipantStatusResponse(BaseModel):
    tournament_id: UUID
    hotkey: str
    participant_type: str
    registration_order: int
    status: str
    registered_at: datetime
    github_repository: Optional[str] = None
    docker_image_tag: Optional[str] = None
    miner_database_name: Optional[str] = None
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None


class RegistrationErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[dict] = None