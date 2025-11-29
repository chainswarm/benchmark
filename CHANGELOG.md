# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [0.1.1] - 2025-11-29

### Changed

- **Jobs module**: Migrated to use common celery/job/task infrastructure from `chainswarm_core.jobs`
  - All tasks now extend `BaseTask` directly from `chainswarm_core.jobs` instead of using local `BaseDataPipelineTask`
  - Removed `packages/jobs/base/base_task.py` (redundant alias file)
  - Removed `packages/utils/decorators.py` (now using `chainswarm_core.observability.log_errors`)
  - Standardized imports across all 12 task files to use `chainswarm_core.jobs.BaseTask`

- **Celery app** (`packages/jobs/celery_app.py`):
  - Now uses `create_celery_app()` from `chainswarm_core.jobs`
  - Removed manual celery configuration and loguru integration (handled by core)

- **Base module exports** (`packages/jobs/base/__init__.py`):
  - Now re-exports `BaseTask`, `BaseTaskContext`, `BaseTaskResult` from `chainswarm_core.jobs`
  - Added `BenchmarkTaskContext` extending `BaseTaskContext`

- **Package initialization** (`packages/__init__.py`):
  - Simplified to only load dotenv
  - Removed redundant `setup_logger` (now using `chainswarm_core.observability.setup_logger`)

- **Scripts**:
  - `scripts/tasks/run_benchmark_initialization.py` - Updated to use `BenchmarkTaskContext`

### Dependencies

- Added `chainswarm-core>=0.1.8`

## [0.1.0] - 2025-11-25

- Initial commit
 