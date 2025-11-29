from dataclasses import dataclass
from typing import Optional

from chainswarm_core.jobs import BaseTaskContext

__all__ = ["BenchmarkTaskContext"]


@dataclass
class BenchmarkTaskContext(BaseTaskContext):
    pass