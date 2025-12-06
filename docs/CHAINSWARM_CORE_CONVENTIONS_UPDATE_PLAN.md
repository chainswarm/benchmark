# Benchmark chainswarm_core Conventions Update Plan

This document outlines the specific changes needed to align the `benchmark` project with `analytics-pipeline` conventions for `chainswarm_core` usage.

---

## 1. Update `BenchmarkTaskContext` with Domain-Specific Fields

**File:** `benchmark/packages/jobs/base/task_models.py`

**Change:** Add benchmark-specific fields to the task context dataclass.

```python
from dataclasses import dataclass
from typing import Optional

from chainswarm_core.jobs import BaseTaskContext as CoreBaseTaskContext, BaseTaskResult


@dataclass
class BenchmarkTaskContext(CoreBaseTaskContext):
    """Extended task context with benchmark-specific fields."""
    hotkey: Optional[str] = None
    image_type: Optional[str] = None
    epoch_id: Optional[str] = None
    github_repository: Optional[str] = None
    docker_image_tag: Optional[str] = None
    miner_database_name: Optional[str] = None


__all__ = ["BenchmarkTaskContext", "BaseTaskResult"]
```

---

## 2. Update Repository Imports - Add `row_to_dict`

### 2.1 `miner_registry_repository.py`

**File:** `benchmark/packages/storage/repositories/miner_registry_repository.py`

**Change Line 8:** Update import
```python
# FROM:
from chainswarm_core.db import BaseRepository

# TO:
from chainswarm_core.db import BaseRepository, row_to_dict
```

### 2.2 `benchmark_epoch_repository.py`

**File:** `benchmark/packages/storage/repositories/benchmark_epoch_repository.py`

**Change Line 9:** Update import
```python
# FROM:
from chainswarm_core.db import BaseRepository

# TO:
from chainswarm_core.db import BaseRepository, row_to_dict
```

### 2.3 `miner_database_repository.py`

**File:** `benchmark/packages/storage/repositories/miner_database_repository.py`

**Change Line 8:** Update import
```python
# FROM:
from chainswarm_core.db import BaseRepository

# TO:
from chainswarm_core.db import BaseRepository, row_to_dict
```

### 2.4 `benchmark_results_repository.py`

**File:** `benchmark/packages/storage/repositories/benchmark_results_repository.py`

**Change Line 9:** Update import
```python
# FROM:
from chainswarm_core.db import BaseRepository

# TO:
from chainswarm_core.db import BaseRepository, row_to_dict
```

---

## 3. Remove Self-Creating Client Pattern from Repositories

### 3.1 `miner_registry_repository.py`

**File:** `benchmark/packages/storage/repositories/miner_registry_repository.py`

**Change Lines 16-23:** Remove default client creation
```python
# FROM:
def __init__(self, client: Client = None):
    if client is None:
        client = get_client(
            host=os.environ['VALIDATOR_CH_HOST'],
            port=int(os.environ['VALIDATOR_CH_PORT']),
            database='default'
        )
    super().__init__(client)

# TO:
def __init__(self, client: Client):
    super().__init__(client)
```

**Also remove:** `import os` and `from clickhouse_connect import get_client` if no longer used.

### 3.2 `benchmark_epoch_repository.py`

**File:** `benchmark/packages/storage/repositories/benchmark_epoch_repository.py`

**Change Lines 18-25:** Remove default client creation
```python
# FROM:
def __init__(self, client: Client = None):
    if client is None:
        client = get_client(
            host=os.environ['VALIDATOR_CH_HOST'],
            port=int(os.environ['VALIDATOR_CH_PORT']),
            database='default'
        )
    super().__init__(client)

# TO:
def __init__(self, client: Client):
    super().__init__(client)
```

**Also remove:** `import os` and `from clickhouse_connect import get_client` if no longer used.

---

## 4. Update Row-to-Object Conversions to Use `row_to_dict`

### 4.1 `miner_registry_repository.py`

**File:** `benchmark/packages/storage/repositories/miner_registry_repository.py`

**Change `get_active_miners` method (Lines 46-55):**
```python
# FROM:
for row in result.result_rows:
    miners.append(Miner(
        hotkey=row[0],
        image_type=ImageType(row[1]),
        github_repository=row[2],
        registered_at=row[3],
        last_updated_at=row[4],
        status=MinerStatus(row[5]),
        validation_error=row[6]
    ))

# TO:
for row in result.result_rows:
    data = row_to_dict(row, result.column_names)
    miners.append(Miner(
        hotkey=data['hotkey'],
        image_type=ImageType(data['image_type']),
        github_repository=data['github_repository'],
        registered_at=data['registered_at'],
        last_updated_at=data['last_updated_at'],
        status=MinerStatus(data['status']),
        validation_error=data['validation_error']
    ))
```

**Apply same pattern to:** `get_all_miners`, `get_miner` methods.

### 4.2 `benchmark_epoch_repository.py`

**File:** `benchmark/packages/storage/repositories/benchmark_epoch_repository.py`

**Change `_row_to_epoch` method (Lines 151-163):**
```python
# FROM:
def _row_to_epoch(self, row) -> BenchmarkEpoch:
    return BenchmarkEpoch(
        epoch_id=UUID(row[0]) if isinstance(row[0], str) else row[0],
        hotkey=row[1],
        image_type=ImageType(row[2]),
        # ...
    )

# TO:
def _row_to_epoch(self, row, column_names) -> BenchmarkEpoch:
    data = row_to_dict(row, column_names)
    return BenchmarkEpoch(
        epoch_id=UUID(data['epoch_id']) if isinstance(data['epoch_id'], str) else data['epoch_id'],
        hotkey=data['hotkey'],
        image_type=ImageType(data['image_type']),
        start_date=data['start_date'],
        end_date=data['end_date'],
        status=EpochStatus(data['status']),
        docker_image_tag=data['docker_image_tag'],
        miner_database_name=data['miner_database_name'],
        created_at=data['created_at'],
        completed_at=data['completed_at']
    )
```

**Update all callers of `_row_to_epoch` to pass `result.column_names`.**

---

## 5. Remove `setup_logger` from Inside Tasks

### 5.1 `benchmark_initialization_task.py`

**File:** `benchmark/packages/jobs/tasks/benchmark_initialization_task.py`

**Remove Line 16:**
```python
# REMOVE:
setup_logger('benchmark-initialization')
```

**Remove import on Line 7:**
```python
# REMOVE:
from chainswarm_core.observability import setup_logger
```

### 5.2 `miner_database_initialization_task.py`

**File:** `benchmark/packages/jobs/tasks/miner_database_initialization_task.py`

**Remove Line 21:**
```python
# REMOVE:
setup_logger(service_name)
```

**Remove import on Line 7:**
```python
# REMOVE:
from chainswarm_core.observability import setup_logger
```

---

## 6. Update `miner_database_initialization_task.py` to Use Typed Context

**File:** `benchmark/packages/jobs/tasks/miner_database_initialization_task.py`

**Change `execute_task` signature (Line 16):**
```python
# FROM:
def execute_task(self, context: dict):
    hotkey = context['hotkey']
    image_type = ImageType(context['image_type'])

# TO:
from packages.jobs.base import BenchmarkTaskContext

def execute_task(self, context: BenchmarkTaskContext):
    hotkey = context.hotkey
    image_type = ImageType(context.image_type)
```

**Change celery task function (Lines 52-62):**
```python
# FROM:
def miner_database_initialization_task(
    self,
    hotkey: str,
    image_type: str,
):
    context = {
        'hotkey': hotkey,
        'image_type': image_type
    }
    return self.run(context)

# TO:
def miner_database_initialization_task(
    self,
    network: str,
    window_days: int,
    processing_date: str,
    hotkey: str,
    image_type: str,
):
    context = BenchmarkTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date,
        hotkey=hotkey,
        image_type=image_type
    )
    return self.run(context)
```

---

## 7. Update `benchmark_initialization_task.py` Database Connection Pattern

**File:** `benchmark/packages/jobs/tasks/benchmark_initialization_task.py`

**Change Lines 18-19:**
```python
# FROM:
connection_params = get_connection_params('default')
connection_params['database'] = 'benchmark'

# TO:
from packages.storage import DATABASE_PREFIX

connection_params = get_connection_params(context.network, database_prefix=DATABASE_PREFIX)
```

**Update task function to include standard parameters:**
```python
# FROM:
def benchmark_initialization_task(self):
    context = BaseTaskContext()
    return self.run(context)

# TO:
def benchmark_initialization_task(self, network: str, window_days: int, processing_date: str):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date
    )
    return self.run(context)
```

---

## 8. Add FINAL Keyword to SELECT Queries

All repositories should add `FINAL` after table names in SELECT queries for ReplacingMergeTree tables.

### Example changes:

```sql
-- FROM:
SELECT * FROM benchmark_miner_registry WHERE ...

-- TO:
SELECT * FROM benchmark_miner_registry FINAL WHERE ...
```

**Files to update:**
- `benchmark/packages/storage/repositories/miner_registry_repository.py` (Lines 37, 63, 71, 95)
- `benchmark/packages/storage/repositories/benchmark_epoch_repository.py` (Lines 37, 55, 79)
- `benchmark/packages/storage/repositories/miner_database_repository.py`
- `benchmark/packages/storage/repositories/benchmark_results_repository.py`

---

## Summary Checklist

- [x] 1. Update `BenchmarkTaskContext` with domain fields
- [x] 2.1 Add `row_to_dict` import to `miner_registry_repository.py`
- [x] 2.2 Add `row_to_dict` import to `benchmark_epoch_repository.py`
- [x] 2.3 Add `row_to_dict` import to `miner_database_repository.py`
- [x] 2.4 Add `row_to_dict` import to `benchmark_results_repository.py`
- [x] 3.1 Remove self-creating client in `miner_registry_repository.py`
- [x] 3.2 Remove self-creating client in `benchmark_epoch_repository.py`
- [x] 4.1 Use `row_to_dict` in `miner_registry_repository.py` methods
- [x] 4.2 Use `row_to_dict` in `benchmark_epoch_repository.py` methods
- [x] 5.1 Remove `setup_logger` from `benchmark_initialization_task.py`
- [x] 5.2 Remove `setup_logger` from `miner_database_initialization_task.py`
- [x] 6. Update `miner_database_initialization_task.py` to use typed context
- [x] 7. Update `benchmark_initialization_task.py` database connection pattern
- [x] 8. Add FINAL keyword to all SELECT queries

---

## Additional Task Updates Completed

The following task files were also updated to use `BenchmarkTaskContext` and follow the analytics-pipeline conventions:

- [x] `benchmark_orchestrator_task.py` - Fixed invalid base class, added typed context and client handling
- [x] `benchmark_scoring_task.py` - Added typed context and proper client handling
- [x] `docker_build_task.py` - Added typed context
- [x] `benchmark_validation_task.py` - Added typed context and client handling
- [x] `benchmark_test_execution_task.py` - Added typed context and client handling
- [x] `container_run_task.py` - Added typed context
- [x] `code_analysis_task.py` - Added typed context
- [x] `dataset_preparation_task.py` - Added typed context
- [x] `repository_clone_task.py` - Added typed context
- [x] `benchmark_cleanup_task.py` - Added typed context and client handling

**Completion Date:** 2025-12-05

---

## Iteration 2 Updates (2025-12-05)

### Completed

- [x] **`miner_database_initialization_task.py`**: Added `database_prefix=DATABASE_PREFIX` parameter to `get_connection_params()` call
- [x] **`miner_database_initialization_task.py`**: Added `create_database(connection_params)` call before ClientFactory (matching analytics-pipeline pattern)
- [x] **`run_benchmark_initialization.py`**: Removed redundant `logger.info()` after task execution (task handles its own logging)
- [x] **`run_benchmark_initialization.py`**: Fixed service_name to include network: `f'benchmark-{args.network}-initialization'`
- [x] **`run_benchmark_initialization.py`**: Removed unused `loguru` import

---

## Iteration 3 - Completed (2025-12-05)

### Completed

- [x] **`benchmark_validation_task.py` Lines 120, 157** - Added `database_prefix=DATABASE_PREFIX` parameter to miner database connections
- [x] **`benchmark_validation_task.py` Lines 134-139, 169-170** - Updated to use `row_to_dict` pattern instead of index-based access
- [x] **Import update** - Added `row_to_dict` import from `chainswarm_core.db`

### Design Decision: Miner Database Prefix

The miner databases use the same `DATABASE_PREFIX` as the main benchmark database. This is consistent with `miner_database_initialization_task.py` which uses:
```python
connection_params = get_connection_params(hotkey, database_prefix=DATABASE_PREFIX)
```

The `miner_database` parameter passed to validation tasks is the hotkey, and `get_connection_params` combines it with `DATABASE_PREFIX` to create the full database name (e.g., `benchmark_<hotkey>`).

### Verification Results

After Iteration 3, all tasks now consistently:
- Use `database_prefix=DATABASE_PREFIX` for all `get_connection_params` calls
- Use `row_to_dict` for row-to-object conversion instead of index-based access
- No remaining `setup_logger` calls inside task modules

---

## Iteration 4 - Completed (2025-12-05)

### Completed

- [x] **`task_models.py`** - Added docstring documenting field naming convention:
  - `image_tag` / `miner_database`: Runtime references passed between tasks
  - `docker_image_tag` / `miner_database_name`: Persisted field names in epoch/result models
  - Documented that duplication exists for compatibility with different contexts (task passing vs database persistence)

- [x] **Verified miner output tables schema** - Checked `miner_analytics_schema.sql` and `miner_ml_schema.sql`:
  - `miner_output_patterns` uses `ENGINE = MergeTree()` (not ReplacingMergeTree)
  - `miner_risk_scores` uses `ENGINE = MergeTree()` (not ReplacingMergeTree)
  - **Result:** FINAL keyword is NOT needed for these queries

- [x] **`benchmark_validation_task.py`** - Added TODO comment for graceful shutdown consideration:
  ```python
  # TODO: For long-running validation, consider checking chainswarm_core.terminate_event.is_set()
  #       to support graceful shutdown of workers. This would allow early termination
  #       during validation loops if the worker is shutting down.
  ```

### Deferred / Not Applicable

- **Move query logic to repositories** - Keeping inline SQL for miner-generated tables is appropriate since:
  - These are miner-created tables, not benchmark system tables
  - Queries are simple count/select operations
  - Creates clear separation between system repositories and miner data access

---

## Alignment Status: COMPLETE ✅

After 4 iterations, the benchmark project is now fully aligned with chainswarm_core conventions:

### Verified Patterns
1. ✅ All `get_connection_params()` calls use `database_prefix=DATABASE_PREFIX`
2. ✅ All row-to-object conversions use `row_to_dict()` pattern (no `row[0]` indexing)
3. ✅ No `setup_logger()` calls inside task modules (only in script runners)
4. ✅ All tasks use typed `BenchmarkTaskContext` (not dict)
5. ✅ All SELECT queries on ReplacingMergeTree tables use FINAL keyword
6. ✅ Client lifecycle managed via `ClientFactory.client_context()`
7. ✅ Field naming conventions documented

### Future Considerations (Optional)
- Implement `terminate_event` checking for graceful shutdown in long-running tasks
- Consider moving miner table queries to dedicated repository if access patterns grow complex

---

## Conventions Reference

### Import Pattern (analytics-pipeline standard)
```python
from chainswarm_core import ClientFactory, create_database
from chainswarm_core.db import get_connection_params, BaseRepository, row_to_dict
from chainswarm_core.jobs import BaseTask, BaseTaskContext
from chainswarm_core.observability import setup_logger, log_errors
```

### Task Initialization Pattern
```python
connection_params = get_connection_params(context.network, database_prefix=DATABASE_PREFIX)
create_database(connection_params)  # Create if not exists

client_factory = ClientFactory(connection_params)
with client_factory.client_context() as client:
    # Use client
```

### Script Runner Pattern
```python
service_name = f'{project}-{args.network}-{task_name}'
setup_logger(service_name)

task = TaskClass()
task.execute_task(context)
# No extra logging - task handles its own
```