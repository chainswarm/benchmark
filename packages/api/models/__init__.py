"""
Tournament API response models.

Exports all Pydantic models for API responses.
"""

from packages.api.models.tournament_responses import (
    # List Tournaments Response
    TournamentWinnerSummary,
    TournamentListItem,
    PaginationInfo,
    TournamentsListResponse,
    # Tournament Details Response
    TournamentSchedule,
    TournamentConfiguration,
    TournamentBaseline,
    TournamentParticipantsSummary,
    TournamentResultsSummary,
    TournamentDetailsResponse,
    # Leaderboard Response
    ParticipantScores,
    ParticipantStats,
    LeaderboardEntry,
    LeaderboardResponse,
    # Daily Details Response
    SyntheticPatterns,
    NoveltyPatterns,
    DataValidation,
    RunPerformance,
    BaselineComparison,
    DisqualificationInfo,
    NetworkRun,
    ParticipantDayRun,
    DayDataset,
    TournamentDayResponse,
    # Participant History Response
    ParticipantRegistration,
    ParticipantStatusInfo,
    ParticipantResult,
    NetworkDayPerformance,
    DailyPerformance,
    ParticipantHistoryResponse,
)

from packages.api.models.registration_responses import (
    RegistrationRequest,
    RegistrationResponse,
    ParticipantStatusResponse,
    RegistrationErrorResponse,
)

__all__ = [
    # List Tournaments Response
    "TournamentWinnerSummary",
    "TournamentListItem",
    "PaginationInfo",
    "TournamentsListResponse",
    # Tournament Details Response
    "TournamentSchedule",
    "TournamentConfiguration",
    "TournamentBaseline",
    "TournamentParticipantsSummary",
    "TournamentResultsSummary",
    "TournamentDetailsResponse",
    # Leaderboard Response
    "ParticipantScores",
    "ParticipantStats",
    "LeaderboardEntry",
    "LeaderboardResponse",
    # Daily Details Response
    "SyntheticPatterns",
    "NoveltyPatterns",
    "DataValidation",
    "RunPerformance",
    "BaselineComparison",
    "DisqualificationInfo",
    "NetworkRun",
    "ParticipantDayRun",
    "DayDataset",
    "TournamentDayResponse",
    # Participant History Response
    "ParticipantRegistration",
    "ParticipantStatusInfo",
    "ParticipantResult",
    "NetworkDayPerformance",
    "DailyPerformance",
    "ParticipantHistoryResponse",
    # Registration Response
    "RegistrationRequest",
    "RegistrationResponse",
    "ParticipantStatusResponse",
    "RegistrationErrorResponse",
]