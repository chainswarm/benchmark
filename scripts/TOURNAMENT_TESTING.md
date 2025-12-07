# Tournament Manual Testing Guide

This guide explains how to manually test the entire tournament lifecycle step-by-step using CLI scripts. No Celery scheduler needed - you control the timing.

## Prerequisites

```bash
# 1. ClickHouse running
docker-compose -f ops/docker-compose.yml up -d clickhouse

# 2. Docker daemon running (for container execution)
docker info

# 3. S3/MinIO with test datasets (optional for real execution)
```

---

## Step 0: Initialize Database Schema

Before any testing, run the initialization script to create all tables (core benchmark + tournament):

```bash
python scripts/tasks/run_benchmark_initialization.py --network default
```

**Expected output:**
```
INFO     | Initializing benchmark database for default
INFO     | Running core migrations (8 tables)...
INFO     | Running tournament migrations (4 tables)...
INFO     | Benchmark schema initialization completed (core + tournament tables)
```

**Tables created:**
- Core: `benchmark_miner_registry`, `benchmark_miner_databases`, `benchmark_epochs`, `benchmark_analytics_daily_runs`, `benchmark_ml_daily_runs`, `benchmark_analytics_baseline_runs`, `benchmark_ml_baseline_runs`, `benchmark_scores`
- Tournament: `baseline_registry`, `tournament_tournaments`, `tournament_participants`, `tournament_results`

This replaces running individual `clickhouse-client` commands manually.

## Quick Start: Full Tournament Simulation

```bash
# Run entire simulation (7 days of competition)
./scripts/simulate_tournament.sh
```

Or follow the manual steps below.

---

## Step-by-Step Manual Testing

### Phase 1: Seed the Initial Baseline

Before any tournament can run, you need a baseline image to compete against.

```bash
python scripts/tasks/run_baseline_seed.py \
  --image-type analytics \
  --version "v1.0.0" \
  --github-repository "https://github.com/chainswarm/analytics-baseline" \
  --docker-image-tag "chainswarm/analytics-baseline:v1.0.0"
```

**Expected output:**
```
✅ Baseline created with ID: 550e8400-e29b-41d4-a716-446655440000
   Status: ACTIVE
```

---

### Phase 2: Create a Tournament

Create a new tournament with specific date boundaries.

```bash
# Create tournament starting registration Jan 5, competition Jan 11-17
python scripts/tasks/run_tournament_create.py \
  --name "Analytics Tournament Q1 2024" \
  --image-type analytics \
  --registration-start 2024-01-05 \
  --registration-end 2024-01-10 \
  --max-participants 5 \
  --epoch-days 7
```

**Expected output:**
```
✅ Tournament created!
   ID: 660e8400-e29b-41d4-a716-446655440001
   Name: Analytics Tournament Q1 2024
   Status: DRAFT
   Baseline participant auto-registered (order=0)
```

**Save the tournament ID** - you'll use it in subsequent commands.

```bash
export TOURNAMENT_ID="660e8400-e29b-41d4-a716-446655440001"
```

---

### Phase 3: Open Registration (Simulate Jan 5)

The orchestrator checks dates and transitions DRAFT → REGISTRATION.

```bash
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-05
```

**Expected output:**
```
🔄 Processing tournament: Analytics Tournament Q1 2024
   Current status: DRAFT
   
   ✓ Date check: 2024-01-05 >= 2024-01-05 (registration_start)
   ✓ Transitioning: DRAFT → REGISTRATION
   
✅ Tournament now accepting registrations
```

---

### Phase 4: Register Multiple Miners

Now miners can register. Register as many as you want to test.

```bash
# Register miner 1
python scripts/tasks/run_tournament_register.py \
  --tournament-id $TOURNAMENT_ID \
  --hotkey "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty" \
  --github-repository "https://github.com/miner1/analytics-solution" \
  --docker-image-tag "miner1/analytics:latest"

# Register miner 2
python scripts/tasks/run_tournament_register.py \
  --tournament-id $TOURNAMENT_ID \
  --hotkey "5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y" \
  --github-repository "https://github.com/miner2/analytics-solution" \
  --docker-image-tag "miner2/analytics:latest"

# Register miner 3
python scripts/tasks/run_tournament_register.py \
  --tournament-id $TOURNAMENT_ID \
  --hotkey "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy" \
  --github-repository "https://github.com/miner3/analytics-solution" \
  --docker-image-tag "miner3/analytics:latest"
```

**Expected output for each:**
```
✅ Miner registered!
   Hotkey: 5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty
   Registration order: 1
   Status: REGISTERED
```

**Note:** Registration order starts at 1. Baseline is always order=0.

---

### Phase 5: Start Competition (Simulate Jan 11)

After registration closes, orchestrator transitions REGISTRATION → IN_PROGRESS.

```bash
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-11
```

**Expected output:**
```
🔄 Processing tournament: Analytics Tournament Q1 2024
   Current status: REGISTRATION
   
   ✓ Date check: 2024-01-11 > 2024-01-10 (registration_end)
   ✓ Creating benchmark epoch with tournament_id
   ✓ Activating all participants (found: 4)
   ✓ Transitioning: REGISTRATION → IN_PROGRESS
   
✅ Competition started! Day 1 of 7
```

---

### Phase 6: Execute Daily Benchmarks

Run benchmarks for each competition day. All participants run sequentially.

```bash
# Day 1
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-11

# Day 2
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-12

# Day 3
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-13

# Day 4
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-14

# Day 5
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-15

# Day 6
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-16

# Day 7
python scripts/tasks/run_tournament_day_execution.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-17
```

**Expected output for each day:**
```
📅 Day Execution: 2024-01-11
   Tournament: Analytics Tournament Q1 2024
   
   Running benchmarks for 4 participants...
   
   [1/4] Baseline (order=0)
         ├─ Network: torus, Window: 30 days
         │  ✓ Execution time: 245.3s
         │  ✓ Recall: 0.847
         │  ✓ Data correctness: PASSED
         ├─ Network: torus, Window: 90 days
         │  ✓ Execution time: 312.1s
         │  ✓ Recall: 0.823
         │  ✓ Data correctness: PASSED
         └─ ...
   
   [2/4] Miner 5FHneW46... (order=1)
         ├─ Network: torus, Window: 30 days
         │  ✓ Execution time: 198.7s
         │  ✓ Recall: 0.891
         │  ✓ Data correctness: PASSED
         └─ ...
   
   [3/4] Miner 5FLSigC9... (order=2)
         ...
   
   [4/4] Miner 5DAAnrj7... (order=3)
         ...

✅ Day 1 completed. All runs recorded.
```

---

### Phase 7: Trigger Scoring (Simulate Jan 18)

After competition ends, orchestrator transitions IN_PROGRESS → SCORING.

```bash
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-18
```

**Expected output:**
```
🔄 Processing tournament: Analytics Tournament Q1 2024
   Current status: IN_PROGRESS
   
   ✓ Date check: 2024-01-18 > 2024-01-17 (competition_end)
   ✓ Completing epoch
   ✓ Transitioning: IN_PROGRESS → SCORING
   ✓ Triggering scoring task...
```

---

### Phase 8: Calculate Scores and Rankings

Run the scoring task to compute final results.

```bash
python scripts/tasks/run_tournament_scoring.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics
```

**Expected output:**
```
📊 Tournament Scoring: Analytics Tournament Q1 2024

   Calculating scores for 4 participants...
   
   Baseline average execution time: 278.5s
   
   ┌────────────────────────────┬─────────┬─────────┬─────────┬─────────┬──────┐
   │ Participant                │ Pattern │ Data    │ Perf    │ Final   │ Rank │
   │                            │ (50%)   │ (30%)   │ (20%)   │ Score   │      │
   ├────────────────────────────┼─────────┼─────────┼─────────┼─────────┼──────┤
   │ 5FHneW46... (miner)        │ 0.891   │ 1.000   │ 0.923   │ 0.8309  │ 1    │
   │ 5DAAnrj7... (miner)        │ 0.867   │ 1.000   │ 0.876   │ 0.8089  │ 2    │
   │ BASELINE                   │ 0.835   │ 1.000   │ 1.000   │ 0.7175  │ 3    │
   │ 5FLSigC9... (miner)        │ 0.712   │ 1.000   │ 0.654   │ 0.6868  │ 4    │
   └────────────────────────────┴─────────┴─────────┴─────────┴─────────┴──────┘
   
   🏆 Winner: 5FHneW46... (beat baseline by 15.8%)
   
✅ Results saved to tournament_results table
✅ Tournament status: COMPLETED
```

---

### Phase 9: Promote Winner as New Baseline (Optional)

If the winner beat the baseline, promote their code as the new baseline.

```bash
python scripts/tasks/run_baseline_promotion.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics
```

**Expected output:**
```
🔄 Baseline Promotion Check
   Tournament: Analytics Tournament Q1 2024
   Winner: 5FHneW46...
   Baseline beaten: YES
   
   ✓ Forking winner repository...
   ✓ Building new baseline image...
   ✓ Creating new baseline record (v1.1.0)
   ✓ Deprecating old baseline (v1.0.0)
   
✅ New baseline promoted!
   Version: v1.1.0
   Image: chainswarm/analytics-baseline:v1.1.0
   Origin: Tournament "Analytics Tournament Q1 2024"
```

---

## Execution Order Reference

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           TOURNAMENT EXECUTION ORDER                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  0. run_benchmark_initialization - Create all database tables (one-time)     │
│                                                                               │
│  1. run_baseline_seed.py        - Create initial baseline (one-time setup)   │
│                                                                               │
│  2. run_tournament_create.py    - Create tournament with dates               │
│                                                                               │
│  3. run_tournament_orchestrator - DRAFT → REGISTRATION (test-date >= start)  │
│                                                                               │
│  4. run_tournament_register.py  - Register miners (repeat for each miner)    │
│     run_tournament_register.py                                                │
│     run_tournament_register.py                                                │
│                                                                               │
│  5. run_tournament_orchestrator - REGISTRATION → IN_PROGRESS                 │
│                                                                               │
│  6. run_tournament_day_execution - Day 1 benchmarks                          │
│     run_tournament_day_execution - Day 2 benchmarks                          │
│     run_tournament_day_execution - Day 3 benchmarks                          │
│     run_tournament_day_execution - Day 4 benchmarks                          │
│     run_tournament_day_execution - Day 5 benchmarks                          │
│     run_tournament_day_execution - Day 6 benchmarks                          │
│     run_tournament_day_execution - Day 7 benchmarks                          │
│                                                                               │
│  7. run_tournament_orchestrator - IN_PROGRESS → SCORING                      │
│                                                                               │
│  8. run_tournament_scoring.py   - Calculate final scores                     │
│                                                                               │
│  9. run_baseline_promotion.py   - Promote winner (if beat baseline)          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Available Scripts Reference

| Script | Purpose | Key Arguments |
|--------|---------|---------------|
| `run_benchmark_initialization.py` | Create all database tables | `--network` |
| `run_baseline_seed.py` | Create initial baseline | `--image-type`, `--version`, `--github-repository`, `--docker-image-tag` |
| `run_tournament_create.py` | Create new tournament | `--name`, `--image-type`, `--registration-start`, `--registration-end`, `--max-participants`, `--epoch-days` |
| `run_tournament_register.py` | Register miner for tournament | `--tournament-id`, `--hotkey`, `--github-repository`, `--docker-image-tag` |
| `run_tournament_orchestrator.py` | Advance tournament lifecycle | `--tournament-id`, `--image-type`, `--test-date`, `--dry-run` |
| `run_tournament_day_execution.py` | Execute single day's benchmarks | `--tournament-id`, `--image-type`, `--test-date` |
| `run_tournament_scoring.py` | Calculate final scores/rankings | `--tournament-id`, `--image-type` |
| `run_baseline_promotion.py` | Promote winner as new baseline | `--tournament-id`, `--image-type` |

---

## The `--test-date` Parameter

The `--test-date` parameter simulates what "today" is, allowing you to:

1. **Skip waiting** - No need to wait real calendar days
2. **Test date transitions** - Verify lifecycle changes at exact boundaries
3. **Run multiple days quickly** - Execute a 7-day competition in minutes

**Without `--test-date`:** Uses `datetime.now()` (real time)
**With `--test-date 2024-01-15`:** Pretends today is January 15, 2024

---

## Dry Run Mode

Add `--dry-run` to any orchestrator command to see what would happen without making changes:

```bash
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID \
  --image-type analytics \
  --test-date 2024-01-18 \
  --dry-run
```

**Output:**
```
🔍 DRY RUN - No changes will be made

   Current status: IN_PROGRESS
   Test date: 2024-01-18
   Competition end: 2024-01-17
   
   Would transition: IN_PROGRESS → SCORING
   Would complete epoch
   Would trigger scoring task
```

---

## Troubleshooting

### "Tournament not found"
Verify tournament ID exists:
```bash
clickhouse-client --query "SELECT tournament_id, name, status FROM tournament_tournaments"
```

### "No active baseline found"
Run baseline seed first:
```bash
python scripts/tasks/run_baseline_seed.py --image-type analytics
```

### "Registration closed"
Check dates - your test-date may be past registration_end:
```bash
clickhouse-client --query "SELECT registration_start, registration_end FROM tournament_tournaments WHERE tournament_id = '$TOURNAMENT_ID'"
```

### "Participant already registered"
Each hotkey can only register once per tournament. Check existing registrations:
```bash
clickhouse-client --query "SELECT hotkey, registration_order FROM tournament_participants WHERE tournament_id = '$TOURNAMENT_ID'"
```

### "Table doesn't exist"
Run the initialization script first:
```bash
python scripts/tasks/run_benchmark_initialization.py --network default
```

---

## Complete Quick Reference

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# TOURNAMENT TESTING QUICK REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

# Step 0: Initialize database (one-time)
python scripts/tasks/run_benchmark_initialization.py --network default

# Step 1: Seed baseline (one-time)
python scripts/tasks/run_baseline_seed.py --image-type analytics --version v1.0.0 \
  --github-repository "https://github.com/org/baseline" \
  --docker-image-tag "org/baseline:v1.0.0"

# Step 2: Create tournament
export TOURNAMENT_ID=$(python scripts/tasks/run_tournament_create.py \
  --name "Test Tournament" --image-type analytics \
  --registration-start 2024-01-05 --registration-end 2024-01-10 \
  | grep "ID:" | awk '{print $2}')

# Step 3: Open registration
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID --image-type analytics --test-date 2024-01-05

# Step 4: Register miners
python scripts/tasks/run_tournament_register.py --tournament-id $TOURNAMENT_ID \
  --hotkey "miner1_hotkey" --github-repository "https://github.com/miner1/repo" \
  --docker-image-tag "miner1/image:latest"

python scripts/tasks/run_tournament_register.py --tournament-id $TOURNAMENT_ID \
  --hotkey "miner2_hotkey" --github-repository "https://github.com/miner2/repo" \
  --docker-image-tag "miner2/image:latest"

# Step 5: Start competition
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID --image-type analytics --test-date 2024-01-11

# Step 6: Run daily benchmarks (repeat for each day)
for day in 11 12 13 14 15 16 17; do
  python scripts/tasks/run_tournament_day_execution.py \
    --tournament-id $TOURNAMENT_ID --image-type analytics --test-date 2024-01-$day
done

# Step 7: Trigger scoring
python scripts/tasks/run_tournament_orchestrator.py \
  --tournament-id $TOURNAMENT_ID --image-type analytics --test-date 2024-01-18

# Step 8: Calculate final scores
python scripts/tasks/run_tournament_scoring.py \
  --tournament-id $TOURNAMENT_ID --image-type analytics

# Step 9: Promote winner (if beat baseline)
python scripts/tasks/run_baseline_promotion.py \
  --tournament-id $TOURNAMENT_ID --image-type analytics
```