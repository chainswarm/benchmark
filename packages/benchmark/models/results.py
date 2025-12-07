from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID

from packages.benchmark.models.miner import ImageType


class RunStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    TIMEOUT = 'timeout'
    FAILED = 'failed'


@dataclass
class AnalyticsDailyRun:
    run_id: UUID
    epoch_id: UUID
    hotkey: str
    test_date: date
    network: str
    window_days: int
    processing_date: date
    execution_time_seconds: float
    container_exit_code: int
    gpu_memory_peak_mb: float
    synthetic_patterns_expected: int
    synthetic_patterns_found: int
    synthetic_patterns_recall: float
    novelty_patterns_reported: int
    novelty_patterns_validated: int
    novelty_addresses_valid: bool
    novelty_connections_valid: bool
    all_addresses_exist: bool
    all_connections_exist: bool
    data_correctness_passed: bool
    status: RunStatus
    error_message: Optional[str]
    created_at: datetime
    # Tournament fields
    tournament_id: Optional[UUID] = None
    participant_type: str = 'miner'  # 'miner' or 'baseline'
    run_order: int = 0
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None


@dataclass
class MLDailyRun:
    run_id: UUID
    epoch_id: UUID
    hotkey: str
    test_date: date
    network: str
    window_days: int
    processing_date: date
    execution_time_seconds: float
    container_exit_code: int
    gpu_memory_peak_mb: float
    auc_roc: float
    precision_at_recall_80: float
    all_addresses_exist: bool
    data_correctness_passed: bool
    status: RunStatus
    error_message: Optional[str]
    created_at: datetime
    # Tournament fields
    tournament_id: Optional[UUID] = None
    participant_type: str = 'miner'  # 'miner' or 'baseline'
    run_order: int = 0
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None


@dataclass
class AnalyticsBaselineRun:
    run_id: UUID
    baseline_version: str
    test_date: date
    network: str
    window_days: int
    processing_date: date
    execution_time_seconds: float
    synthetic_patterns_expected: int
    synthetic_patterns_found: int
    synthetic_patterns_recall: float
    created_at: datetime


@dataclass
class MLBaselineRun:
    run_id: UUID
    baseline_version: str
    test_date: date
    network: str
    window_days: int
    processing_date: date
    execution_time_seconds: float
    auc_roc: float
    precision_at_recall_80: float
    created_at: datetime


@dataclass
class BenchmarkScore:
    epoch_id: UUID
    hotkey: str
    image_type: ImageType
    data_correctness_all_days: bool
    pattern_accuracy_score: float
    data_correctness_score: float
    performance_score: float
    final_score: float
    rank: int
    baseline_comparison_ratio: float
    all_runs_within_time_limit: bool
    average_execution_time_seconds: float
    calculated_at: datetime


@dataclass
class ValidationResult:
    is_valid: bool
    repo_path: Optional[Path]
    error_message: Optional[str]
    has_dockerfile: bool
    is_obfuscated: bool
    has_malware: bool


@dataclass
class ContainerResult:
    exit_code: int
    execution_time_seconds: float
    gpu_memory_peak_mb: float
    logs: str
    timed_out: bool


@dataclass
class RecallMetrics:
    patterns_expected: int
    patterns_found: int
    recall: float
    matched_pattern_ids: List[str]
    missed_pattern_ids: List[str]


@dataclass
class NoveltyResult:
    patterns_reported: int
    patterns_validated: int
    addresses_valid: bool
    connections_valid: bool
    invalid_addresses: List[str]
    invalid_connections: List[Tuple[str, str]]