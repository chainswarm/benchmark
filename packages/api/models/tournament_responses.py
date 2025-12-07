"""
Pydantic response models for the Tournament API.

These models define the structure of API responses for tournament data,
including list views, details, leaderboards, daily runs, and participant history.
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== List Tournaments Response ====================


class TournamentWinnerSummary(BaseModel):
    """Summary of a tournament winner."""

    hotkey: str = Field(..., description="Winner's hotkey identifier")
    beat_baseline: bool = Field(..., description="Whether the winner beat the baseline")


class TournamentListItem(BaseModel):
    """Single tournament in list view."""

    tournament_id: UUID = Field(..., description="Unique tournament identifier")
    name: str = Field(..., description="Tournament name")
    image_type: str = Field(..., description="Type: 'analytics' or 'ml'")
    status: str = Field(..., description="Current tournament status")
    competition_start: date = Field(..., description="Competition start date")
    competition_end: date = Field(..., description="Competition end date")
    participant_count: int = Field(..., description="Number of participants")
    winner: Optional[TournamentWinnerSummary] = Field(
        None, description="Winner summary if completed"
    )
    created_at: datetime = Field(..., description="Tournament creation timestamp")
    completed_at: Optional[datetime] = Field(
        None, description="Tournament completion timestamp"
    )


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(..., description="Whether more items exist")


class TournamentsListResponse(BaseModel):
    """Response for listing tournaments."""

    tournaments: List[TournamentListItem] = Field(..., description="List of tournaments")
    pagination: PaginationInfo = Field(..., description="Pagination information")


# ==================== Tournament Details Response ====================


class TournamentSchedule(BaseModel):
    """Tournament schedule information."""

    registration_start: date = Field(..., description="Registration opens")
    registration_end: date = Field(..., description="Registration closes")
    competition_start: date = Field(..., description="Competition begins")
    competition_end: date = Field(..., description="Competition ends")


class TournamentConfiguration(BaseModel):
    """Tournament configuration settings."""

    max_participants: int = Field(..., description="Maximum allowed participants")
    epoch_days: int = Field(..., description="Number of competition days per epoch")
    test_networks: List[str] = Field(..., description="Networks to test against")
    test_window_days: List[int] = Field(..., description="Test window sizes in days")


class TournamentBaseline(BaseModel):
    """Baseline information for the tournament."""

    baseline_id: UUID = Field(..., description="Baseline identifier")
    version: str = Field(..., description="Baseline version string")
    hotkey: str = Field(..., description="Baseline hotkey")
    source_tournament_id: Optional[UUID] = Field(
        None, description="Tournament this baseline originated from"
    )


class TournamentParticipantsSummary(BaseModel):
    """Summary of tournament participants."""

    total: int = Field(..., description="Total registered participants")
    active: int = Field(..., description="Currently active participants")
    disqualified: int = Field(..., description="Disqualified participants")


class TournamentResultsSummary(BaseModel):
    """Summary of tournament results."""

    winner_hotkey: Optional[str] = Field(None, description="Winner's hotkey if determined")
    baseline_beaten: bool = Field(..., description="Whether baseline was beaten")
    current_day: int = Field(..., description="Current competition day")
    days_completed: int = Field(..., description="Number of days completed")


class TournamentDetailsResponse(BaseModel):
    """Detailed tournament information response."""

    tournament_id: UUID = Field(..., description="Unique tournament identifier")
    name: str = Field(..., description="Tournament name")
    image_type: str = Field(..., description="Type: 'analytics' or 'ml'")
    status: str = Field(..., description="Current tournament status")
    schedule: TournamentSchedule = Field(..., description="Tournament schedule")
    configuration: TournamentConfiguration = Field(..., description="Tournament configuration")
    baseline: TournamentBaseline = Field(..., description="Baseline information")
    participants: TournamentParticipantsSummary = Field(
        ..., description="Participant summary"
    )
    results: TournamentResultsSummary = Field(..., description="Results summary")
    created_at: datetime = Field(..., description="Tournament creation timestamp")
    completed_at: Optional[datetime] = Field(
        None, description="Tournament completion timestamp"
    )


# ==================== Leaderboard Response ====================


class ParticipantScores(BaseModel):
    """Scoring breakdown for a participant."""

    final_score: float = Field(..., description="Overall final score")
    pattern_accuracy_score: float = Field(..., description="Pattern detection accuracy score")
    data_correctness_score: float = Field(..., description="Data correctness score")
    performance_score: float = Field(..., description="Execution performance score")


class ParticipantStats(BaseModel):
    """Statistics for a participant."""

    days_completed: int = Field(..., description="Number of days completed")
    total_runs_completed: int = Field(..., description="Total runs executed")
    average_execution_time_seconds: float = Field(
        ..., description="Average execution time in seconds"
    )
    baseline_comparison_ratio: float = Field(
        ..., description="Ratio compared to baseline performance"
    )
    beat_baseline: bool = Field(..., description="Whether participant beat the baseline")
    miners_beaten: int = Field(..., description="Number of other miners beaten")


class LeaderboardEntry(BaseModel):
    """Single entry in the tournament leaderboard."""

    rank: int = Field(..., description="Current rank position")
    hotkey: str = Field(..., description="Participant hotkey")
    participant_type: str = Field(..., description="Type: 'miner' or 'baseline'")
    is_winner: bool = Field(..., description="Whether this participant is the winner")
    is_disqualified: bool = Field(..., description="Whether participant is disqualified")
    disqualification_reason: Optional[str] = Field(
        None, description="Reason for disqualification"
    )
    disqualified_on_day: Optional[int] = Field(
        None, description="Day when disqualification occurred"
    )
    scores: ParticipantScores = Field(..., description="Score breakdown")
    stats: ParticipantStats = Field(..., description="Participant statistics")


class LeaderboardResponse(BaseModel):
    """Tournament leaderboard response."""

    tournament_id: UUID = Field(..., description="Tournament identifier")
    status: str = Field(..., description="Current tournament status")
    leaderboard: List[LeaderboardEntry] = Field(..., description="Ranked participant list")


# ==================== Daily Details Response ====================


class SyntheticPatterns(BaseModel):
    """Synthetic pattern detection results."""

    expected: int = Field(..., description="Number of expected synthetic patterns")
    found: int = Field(..., description="Number of patterns found")
    recall: float = Field(..., description="Recall rate (found/expected)")


class NoveltyPatterns(BaseModel):
    """Novelty pattern detection results."""

    reported: int = Field(..., description="Number of novel patterns reported")
    validated: int = Field(..., description="Number of validated novel patterns")
    addresses_valid: bool = Field(..., description="Whether all addresses are valid")
    connections_valid: bool = Field(..., description="Whether all connections are valid")


class DataValidation(BaseModel):
    """Data validation results for a run."""

    all_addresses_exist: bool = Field(..., description="All addresses exist in dataset")
    all_connections_exist: bool = Field(..., description="All connections exist in dataset")
    data_correctness_passed: bool = Field(..., description="Overall data validation passed")


class RunPerformance(BaseModel):
    """Performance metrics for a run."""

    execution_time_seconds: float = Field(..., description="Total execution time in seconds")
    container_exit_code: int = Field(..., description="Docker container exit code")
    gpu_memory_peak_mb: float = Field(..., description="Peak GPU memory usage in MB")


class BaselineComparison(BaseModel):
    """Comparison metrics against the baseline."""

    synthetic_recall_vs_baseline: float = Field(
        ..., description="Synthetic recall ratio vs baseline"
    )
    novelty_vs_baseline: float = Field(..., description="Novelty ratio vs baseline")
    execution_time_vs_baseline: float = Field(
        ..., description="Execution time ratio vs baseline"
    )


class DisqualificationInfo(BaseModel):
    """Disqualification information for a run."""

    is_disqualified: bool = Field(..., description="Whether run caused disqualification")
    reason: Optional[str] = Field(None, description="Disqualification reason code")
    message: Optional[str] = Field(None, description="Human-readable disqualification message")


class NetworkRun(BaseModel):
    """Results for a single network run."""

    network: str = Field(..., description="Network name")
    window_days: int = Field(..., description="Test window size in days")
    run_id: UUID = Field(..., description="Unique run identifier")
    synthetic_patterns: SyntheticPatterns = Field(
        ..., description="Synthetic pattern results"
    )
    novelty_patterns: NoveltyPatterns = Field(..., description="Novelty pattern results")
    data_validation: DataValidation = Field(..., description="Data validation results")
    performance: RunPerformance = Field(..., description="Performance metrics")
    baseline_comparison: Optional[BaselineComparison] = Field(
        None, description="Baseline comparison if available"
    )
    disqualification: Optional[DisqualificationInfo] = Field(
        None, description="Disqualification info if applicable"
    )
    status: str = Field(..., description="Run status")
    started_at: datetime = Field(..., description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")


class ParticipantDayRun(BaseModel):
    """All runs for a participant on a specific day."""

    run_order: int = Field(..., description="Order of execution for this participant")
    participant_type: str = Field(..., description="Type: 'miner' or 'baseline'")
    hotkey: str = Field(..., description="Participant hotkey")
    status: str = Field(..., description="Overall status for this participant's day")
    network_runs: List[NetworkRun] = Field(..., description="Individual network run results")


class DayDataset(BaseModel):
    """Dataset information for a tournament day."""

    networks_tested: List[str] = Field(..., description="Networks tested on this day")
    window_days_tested: List[int] = Field(..., description="Window sizes tested")
    total_runs: int = Field(..., description="Total number of runs")


class TournamentDayResponse(BaseModel):
    """Detailed response for a specific tournament day."""

    tournament_id: UUID = Field(..., description="Tournament identifier")
    day_number: int = Field(..., description="Day number in the tournament")
    test_date: date = Field(..., description="Date of the test")
    dataset: DayDataset = Field(..., description="Dataset information")
    runs: List[ParticipantDayRun] = Field(..., description="All participant runs")


# ==================== Participant History Response ====================


class ParticipantRegistration(BaseModel):
    """Registration information for a participant."""

    registered_at: datetime = Field(..., description="Registration timestamp")
    registration_order: int = Field(..., description="Order of registration")
    github_repository: Optional[str] = Field(None, description="GitHub repository URL")
    docker_image_tag: Optional[str] = Field(None, description="Docker image tag")


class ParticipantStatusInfo(BaseModel):
    """Current status information for a participant."""

    current_status: str = Field(..., description="Current participant status")
    is_disqualified: bool = Field(..., description="Whether participant is disqualified")
    disqualification_reason: Optional[str] = Field(
        None, description="Reason for disqualification"
    )


class ParticipantResult(BaseModel):
    """Final results for a participant."""

    rank: int = Field(..., description="Final rank")
    is_winner: bool = Field(..., description="Whether this participant won")
    final_score: float = Field(..., description="Final score")
    beat_baseline: bool = Field(..., description="Whether participant beat the baseline")
    miners_beaten: int = Field(..., description="Number of miners beaten")


class NetworkDayPerformance(BaseModel):
    """Performance metrics for a specific network on a specific day."""

    synthetic_recall: float = Field(..., description="Synthetic pattern recall")
    novelty_validated: int = Field(..., description="Number of validated novel patterns")
    execution_time_seconds: float = Field(..., description="Execution time in seconds")
    data_correctness_passed: bool = Field(..., description="Whether data validation passed")


class DailyPerformance(BaseModel):
    """Performance summary for a single day."""

    day_number: int = Field(..., description="Day number")
    test_date: date = Field(..., description="Date of the test")
    networks: Dict[str, NetworkDayPerformance] = Field(
        ..., description="Network name to performance mapping"
    )
    day_score: float = Field(..., description="Score for this day")


class ParticipantHistoryResponse(BaseModel):
    """Full tournament history for a specific participant."""

    tournament_id: UUID = Field(..., description="Tournament identifier")
    hotkey: str = Field(..., description="Participant hotkey")
    participant_type: str = Field(..., description="Type: 'miner' or 'baseline'")
    registration: ParticipantRegistration = Field(
        ..., description="Registration information"
    )
    status: ParticipantStatusInfo = Field(..., description="Current status")
    result: Optional[ParticipantResult] = Field(
        None, description="Final result if tournament completed"
    )
    daily_performance: List[DailyPerformance] = Field(
        ..., description="Daily performance records"
    )