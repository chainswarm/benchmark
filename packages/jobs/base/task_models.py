from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BaseTaskContext:
    """Unified task context with all parameters for pipeline tasks."""
    
    # Core parameters (required)
    network: str
    window_days: Optional[int] = None
    processing_date: Optional[str] = None
    
    # Backfill parameters (optional)
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # Task-specific parameters (optional)
    batch_size: Optional[int] = None

@dataclass
class BaseTaskResult:
    network: str
    window_days: int
    processing_date: str
    status: str


@dataclass
class PriceTaskResult:
    network: str
    status: str