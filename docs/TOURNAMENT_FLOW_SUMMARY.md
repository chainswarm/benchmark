# Tournament System Flow Summary

## Overview

The tournament system enables **synchronized competition** between miners, running on the same data and evaluation criteria to determine who can beat the current baseline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TOURNAMENT LIFECYCLE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   DRAFT → REGISTRATION → IN_PROGRESS → SCORING → COMPLETED                     │
│                                                                                  │
│   ┌─────────┐    ┌──────────────┐    ┌────────────────┐    ┌─────────────┐     │
│   │ Create  │───▶│ Accept Miner │───▶│ Execute Daily  │───▶│  Calculate  │     │
│   │ with    │    │ Registrations│    │ Benchmarks     │    │  Scores &   │     │
│   │ Baseline│    │              │    │                │    │  Rankings   │     │
│   └─────────┘    └──────────────┘    └────────────────┘    └─────────────┘     │
│                                                                │                 │
│                                             ┌──────────────────┴──────────────┐ │
│                                             ▼                                  │ │
│                                   ┌─────────────────┐                         │ │
│                                   │ Promote Winner  │─── If beat baseline     │ │
│                                   │ as New Baseline │                         │ │
│                                   └─────────────────┘                         │ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    baseline_registry ||--o{ tournament_tournaments : "provides baseline"
    tournament_tournaments ||--o{ tournament_participants : "has"
    tournament_tournaments ||--|| benchmark_epochs : "has one"
    benchmark_epochs ||--o{ benchmark_analytics_daily_runs : "contains"
    tournament_tournaments ||--o{ tournament_results : "produces"
    baseline_registry ||--o{ tournament_participants : "baseline entry"

    baseline_registry {
        UUID baseline_id PK
        enum image_type
        string version
        string github_repository
        string docker_image_tag
        enum status
        string originated_from_hotkey
        UUID originated_from_tournament_id
        datetime activated_at
    }

    tournament_tournaments {
        UUID tournament_id PK
        string name
        enum image_type
        date registration_start
        date registration_end
        date competition_start
        date competition_end
        int max_participants
        int epoch_days
        array test_networks
        array test_window_days
        UUID baseline_id FK
        enum status
        int current_day
        string winner_hotkey
        bool baseline_beaten
        datetime created_at
        datetime completed_at
    }

    tournament_participants {
        UUID tournament_id PK,FK
        string hotkey PK
        enum participant_type
        datetime registered_at
        int registration_order
        string github_repository
        string docker_image_tag
        string miner_database_name
        UUID baseline_id FK
        enum status
        bool is_disqualified
        string disqualification_reason
        int disqualified_on_day
        datetime updated_at
    }

    benchmark_epochs {
        UUID epoch_id PK
        string hotkey
        enum image_type
        date start_date
        date end_date
        enum status
        string docker_image_tag
        string miner_database_name
        datetime created_at
        datetime completed_at
        UUID tournament_id FK
    }

    benchmark_analytics_daily_runs {
        UUID run_id PK
        UUID epoch_id FK
        string hotkey
        date test_date
        string network
        int window_days
        float execution_time_seconds
        float synthetic_patterns_recall
        bool data_correctness_passed
        enum status
        UUID tournament_id FK
        string participant_type
        int run_order
        bool is_disqualified
        string disqualification_reason
        datetime created_at
    }

    tournament_results {
        UUID tournament_id PK,FK
        string hotkey PK
        enum participant_type
        float pattern_accuracy_score
        float data_correctness_score
        float performance_score
        float final_score
        bool data_correctness_all_days
        bool all_runs_within_time_limit
        int days_completed
        int total_runs_completed
        float average_execution_time_seconds
        float baseline_comparison_ratio
        int rank
        bool is_winner
        bool beat_baseline
        int miners_beaten
        datetime calculated_at
    }
```

## Execution Flow

### Tournament Lifecycle Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Admin as Admin/Scheduler
    participant Orch as TournamentOrchestratorTask
    participant Repo as TournamentRepository
    participant DayExec as TournamentDayExecutionTask
    participant Docker as DockerManager
    participant Score as TournamentScoringTask
    participant Promo as BaselinePromotionTask

    Note over Admin,Promo: PHASE 1: TOURNAMENT CREATION
    Admin->>Repo: Create tournament (status=DRAFT)
    Admin->>Repo: Insert baseline as participant (order=0)

    Note over Orch,Repo: PHASE 2: REGISTRATION OPEN
    Orch->>Orch: Check current_date >= registration_start
    Orch->>Repo: Update status → REGISTRATION
    
    loop For each miner registration
        Admin->>Repo: Insert miner participant (order=N)
    end

    Note over Orch,Repo: PHASE 3: COMPETITION START
    Orch->>Orch: Check current_date > registration_end
    Orch->>Repo: Create BenchmarkEpoch with tournament_id
    Orch->>Repo: Update epoch status → RUNNING
    Orch->>Repo: Update all participants → ACTIVE
    Orch->>Repo: Update tournament status → IN_PROGRESS

    Note over Orch,Docker: PHASE 4: DAILY EXECUTION (7 days)
    loop For each competition day
        Orch->>DayExec: Trigger tournament_day_execution_task
        DayExec->>Repo: Get participants ordered by registration_order
        
        loop For each participant in order
            DayExec->>DayExec: Prepare dataset
            DayExec->>Docker: Run container
            DayExec->>Repo: Insert AnalyticsDailyRun record
            DayExec->>Repo: Validate results
            DayExec->>Repo: Update run status
        end
    end

    Note over Orch,Score: PHASE 5: SCORING
    Orch->>Orch: Check current_date > competition_end
    Orch->>Repo: Update epoch status → COMPLETED
    Orch->>Repo: Update tournament status → SCORING
    Orch->>Score: Trigger tournament_scoring_task

    Score->>Repo: Get all participant runs
    Score->>Score: Calculate baseline average time
    
    loop For each participant
        Score->>Score: Aggregate all runs
        Score->>Score: Calculate pattern_accuracy (50%)
        Score->>Score: Calculate data_correctness (30%)
        Score->>Score: Calculate performance (20%)
        Score->>Score: Compute final_score
    end
    
    Score->>Score: Rank participants by final_score
    Score->>Score: Determine beat_baseline for each
    Score->>Repo: Insert TournamentResult records
    Score->>Repo: Complete tournament with winner

    Note over Orch,Promo: PHASE 6: BASELINE PROMOTION (if applicable)
    alt Winner beat baseline
        Score->>Promo: Trigger baseline_promotion_task
        Promo->>Promo: Fork winner repository
        Promo->>Promo: Build new baseline image
        Promo->>Repo: Insert new baseline (ACTIVE)
        Promo->>Repo: Deprecate old baseline
    end
```

## Task Descriptions

### 1. TournamentOrchestratorTask

**File:** [`packages/jobs/tasks/tournament_orchestrator_task.py`](../packages/jobs/tasks/tournament_orchestrator_task.py)

**Purpose:** Manages the tournament lifecycle by checking status and triggering appropriate actions.

**Status Transitions:**
| Current Status | Condition | Action | New Status |
|---------------|-----------|--------|------------|
| DRAFT | `current_date >= registration_start` | Open registration | REGISTRATION |
| REGISTRATION | `current_date > registration_end` | Create epoch, activate participants | IN_PROGRESS |
| IN_PROGRESS | `current_date > competition_end` | Complete epoch, trigger scoring | SCORING |
| SCORING | Results exist with winner | Complete tournament | COMPLETED |

### 2. TournamentDayExecutionTask

**File:** [`packages/jobs/tasks/tournament_day_execution_task.py`](../packages/jobs/tasks/tournament_day_execution_task.py)

**Purpose:** Executes daily benchmarks for all participants sequentially.

**Execution Order:**
1. Baseline (registration_order=0) runs first
2. Miners run in registration order (1, 2, 3, ...)
3. Each participant runs for every network/window combination

**Per-Run Operations:**
1. Fetch dataset
2. Run Docker container
3. Validate results
4. Record to `benchmark_analytics_daily_runs`

### 3. TournamentScoringTask

**File:** [`packages/jobs/tasks/tournament_scoring_task.py`](../packages/jobs/tasks/tournament_scoring_task.py)

**Purpose:** Calculates final scores and determines rankings after all days complete.

**Scoring Formula:**
```
final_score = 50% × pattern_accuracy_score
            + 30% × data_correctness_score
            + 20% × performance_score
```

**Score Components:**
| Component | Weight | Calculation |
|-----------|--------|-------------|
| Pattern Accuracy | 50% | `mean(synthetic_patterns_recall)` across all runs |
| Data Correctness | 30% | `1.0` if all runs passed, `0.0` otherwise |
| Performance | 20% | `min(baseline_avg_time / participant_avg_time, 1.0)` |

**Disqualification Criteria:**
- Any run with `data_correctness_passed = false`
- Any run exceeding `BENCHMARK_MAX_EXECUTION_TIME` (default: 3600s)

### 4. BaselinePromotionTask

**File:** [`packages/jobs/tasks/baseline_promotion_task.py`](../packages/jobs/tasks/baseline_promotion_task.py)

**Purpose:** Promotes tournament winner as new baseline if they beat the current baseline.

**Promotion Steps:**
1. Verify winner beat baseline (`tournament.baseline_beaten = true`)
2. Fork winner's GitHub repository
3. Build new baseline Docker image
4. Insert new baseline record (status: ACTIVE)
5. Deprecate old baseline (status: DEPRECATED)

## API Endpoints

### Tournament API (Read-Only)

**Base:** `/api/v1/tournaments`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all tournaments with filtering |
| GET | `/{tournament_id}` | Get tournament details |
| GET | `/{tournament_id}/participants` | List participants |
| GET | `/{tournament_id}/daily-metrics` | Get daily metrics by date |
| GET | `/{tournament_id}/results` | Get final rankings |

### Registration API (Internal)

**Base:** `/api/v1/registration`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tournaments` | Create a new tournament |
| POST | `/tournaments/{tournament_id}/participants` | Register a miner |
| PUT | `/participants/{tournament_id}/{hotkey}/status` | Update participant status |

## CLI Runner Scripts

Runner scripts allow step-by-step testing of tournament tasks.

### run_tournament_create.py

```bash
python scripts/tasks/run_tournament_create.py \
  --name "Analytics Tournament Q1 2024" \
  --image-type analytics \
  --registration-start 2024-01-01 \
  --registration-end 2024-01-07
```

### run_tournament_orchestrator.py

```bash
python scripts/tasks/run_tournament_orchestrator.py \
  --image-type analytics \
  --tournament-id <uuid> \
  --test-date 2024-01-08 \
  --dry-run
```

### run_tournament_day_execution.py

```bash
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id <uuid> \
  --image-type analytics \
  --test-date 2024-01-08
```

### run_tournament_scoring.py

```bash
python scripts/tasks/run_tournament_scoring.py \
  --tournament-id <uuid> \
  --image-type analytics
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TOURNAMENT_MAX_PARTICIPANTS` | 10 | Maximum miners per tournament |
| `TOURNAMENT_EPOCH_DAYS` | 7 | Number of competition days |
| `TOURNAMENT_TEST_NETWORKS` | `torus,bittensor` | Networks to test |
| `TOURNAMENT_TEST_WINDOWS` | `30,90` | Window days to test |
| `BENCHMARK_MAX_EXECUTION_TIME` | 3600 | Max seconds per run |

## Testing Step-by-Step

### Prerequisites

1. ClickHouse database running
2. Redis for Celery (optional for manual testing)
3. Docker daemon running
4. S3/MinIO with test datasets

### Manual Testing Flow

```bash
# 1. Create schema tables
clickhouse-client < packages/storage/schema/baseline_registry.sql
clickhouse-client < packages/storage/schema/tournament_tournaments.sql
clickhouse-client < packages/storage/schema/tournament_participants.sql
clickhouse-client < packages/storage/schema/tournament_results.sql
clickhouse-client < packages/storage/schema/benchmark_epochs.sql
clickhouse-client < packages/storage/schema/benchmark_analytics_daily_runs.sql

# 2. Insert initial baseline
python scripts/tasks/run_baseline_seed.py --image-type analytics

# 3. Create tournament
python scripts/tasks/run_tournament_create.py \
  --name "Test Tournament" \
  --image-type analytics \
  --registration-start $(date +%Y-%m-%d) \
  --registration-end $(date -d "+3 days" +%Y-%m-%d)

# 4. Register test miners
python scripts/tasks/run_tournament_register.py \
  --tournament-id <uuid> \
  --hotkey "test_miner_1" \
  --github-repository "https://github.com/test/miner1"

# 5. Run orchestrator to advance phases
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id <uuid> \
  --image-type analytics \
  --test-date $(date -d "+4 days" +%Y-%m-%d)

# 6. Execute a single day
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id <uuid> \
  --image-type analytics \
  --test-date $(date -d "+4 days" +%Y-%m-%d)

# 7. Run scoring
python scripts/tasks/run_tournament_scoring.py \
  --tournament-id <uuid> \
  --image-type analytics
```

## File Structure

```
packages/
├── benchmark/
│   ├── managers/
│   │   ├── baseline_manager.py      # Baseline forking and building
│   │   └── tournament_manager.py    # Tournament lifecycle logic
│   └── models/
│       ├── baseline.py              # Baseline dataclass
│       ├── epoch.py                 # BenchmarkEpoch dataclass
│       ├── results.py               # AnalyticsDailyRun, RunStatus
│       └── tournament.py            # Tournament, Participant, Result
├── jobs/
│   ├── base/
│   │   └── task_models.py           # TournamentTaskContext
│   └── tasks/
│       ├── baseline_promotion_task.py
│       ├── tournament_day_execution_task.py
│       ├── tournament_orchestrator_task.py
│       └── tournament_scoring_task.py
├── storage/
│   ├── repositories/
│   │   ├── baseline_repository.py
│   │   └── tournament_repository.py
│   └── schema/
│       ├── baseline_registry.sql
│       ├── tournament_tournaments.sql
│       ├── tournament_participants.sql
│       ├── tournament_results.sql
│       ├── benchmark_epochs.sql              # + tournament_id column
│       └── benchmark_analytics_daily_runs.sql # + tournament columns
└── api/
    ├── routers/
    │   ├── tournament_router.py     # Read-only UI API
    │   └── registration_router.py   # Internal registration API
    └── services/
        ├── tournament_service.py
        └── registration_service.py
```

## Key Concepts

### Unified Schema

Tournament runs are stored in the **existing `benchmark_analytics_daily_runs`** table with additional columns:
- `tournament_id` - Links run to a tournament (NULL for individual benchmarks)
- `participant_type` - 'miner' or 'baseline'
- `run_order` - Execution sequence within the day
- `is_disqualified`, `disqualification_reason` - Disqualification tracking

### Sequential Execution

All participants run **sequentially** (not in parallel) to ensure:
- Fair resource allocation
- Consistent timing measurements
- Reproducible results

Baseline always runs first (order=0), then miners in registration order.

### Baseline Beating

A participant "beats baseline" if:
1. They complete all runs with `data_correctness_passed = true`
2. Their `final_score > baseline.final_score`
3. All runs complete within time limit

If the tournament winner beats baseline, their code becomes the new baseline for future tournaments.