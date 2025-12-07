from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from packages.benchmark.models.miner import ImageType


class TournamentStatus(Enum):
    DRAFT = 'draft'
    REGISTRATION = 'registration'
    IN_PROGRESS = 'in_progress'
    SCORING = 'scoring'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class ParticipantType(Enum):
    MINER = 'miner'
    BASELINE = 'baseline'


class ParticipantStatus(Enum):
    REGISTERED = 'registered'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    FAILED = 'failed'
    DISQUALIFIED = 'disqualified'


@dataclass
class Tournament:
    tournament_id: UUID
    name: str
    image_type: ImageType
    registration_start: date
    registration_end: date
    competition_start: date
    competition_end: date
    max_participants: int
    epoch_days: int
    test_networks: List[str]
    test_window_days: List[int]
    baseline_id: UUID
    status: TournamentStatus
    current_day: int
    created_at: datetime
    winner_hotkey: Optional[str] = None
    baseline_beaten: bool = False
    completed_at: Optional[datetime] = None


@dataclass
class TournamentParticipant:
    tournament_id: UUID
    hotkey: str
    participant_type: ParticipantType
    registered_at: datetime
    registration_order: int
    github_repository: Optional[str]
    docker_image_tag: Optional[str]
    miner_database_name: Optional[str]
    baseline_id: Optional[UUID]
    status: ParticipantStatus
    updated_at: datetime
    # Disqualification fields
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None
    disqualified_on_day: Optional[int] = None


@dataclass
class TournamentResult:
    tournament_id: UUID
    hotkey: str
    participant_type: ParticipantType
    pattern_accuracy_score: float
    data_correctness_score: float
    performance_score: float
    final_score: float
    data_correctness_all_days: bool
    all_runs_within_time_limit: bool
    days_completed: int
    total_runs_completed: int
    average_execution_time_seconds: float
    baseline_comparison_ratio: float
    rank: int
    is_winner: bool
    beat_baseline: bool
    miners_beaten: int
    calculated_at: datetime