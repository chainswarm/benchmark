CREATE TABLE IF NOT EXISTS benchmark_analytics_daily_runs (
    run_id UUID DEFAULT generateUUIDv4(),
    epoch_id UUID,
    hotkey String,
    test_date Date,
    network String,
    window_days UInt16,
    processing_date Date,

    execution_time_seconds Float64,
    container_exit_code Int32,
    gpu_memory_peak_mb Float64,

    synthetic_patterns_expected UInt32,
    synthetic_patterns_found UInt32,
    synthetic_patterns_recall Float64,

    novelty_patterns_reported UInt32,
    novelty_patterns_validated UInt32,
    novelty_addresses_valid Bool,
    novelty_connections_valid Bool,

    all_addresses_exist Bool,
    all_connections_exist Bool,
    data_correctness_passed Bool,

    status Enum('pending', 'running', 'completed', 'timeout', 'failed') DEFAULT 'pending',
    error_message Nullable(String),

    created_at DateTime DEFAULT now(),
    
    -- Tournament tracking columns (optional - null for standalone benchmarks)
    tournament_id Nullable(UUID),
    participant_type Enum('miner', 'baseline') DEFAULT 'miner',
    run_order UInt16 DEFAULT 0,
    is_disqualified Bool DEFAULT false,
    disqualification_reason Nullable(String)
) ENGINE = MergeTree()
ORDER BY (epoch_id, test_date, network);

ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_run_id run_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_hotkey hotkey TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_network network TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_test_date test_date TYPE minmax GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_data_correctness data_correctness_passed TYPE set(0) GRANULARITY 4;

-- Add tournament tracking columns
ALTER TABLE benchmark_analytics_daily_runs ADD COLUMN IF NOT EXISTS tournament_id Nullable(UUID);
ALTER TABLE benchmark_analytics_daily_runs ADD COLUMN IF NOT EXISTS participant_type Enum('miner', 'baseline') DEFAULT 'miner';
ALTER TABLE benchmark_analytics_daily_runs ADD COLUMN IF NOT EXISTS run_order UInt16 DEFAULT 0;
ALTER TABLE benchmark_analytics_daily_runs ADD COLUMN IF NOT EXISTS is_disqualified Bool DEFAULT false;
ALTER TABLE benchmark_analytics_daily_runs ADD COLUMN IF NOT EXISTS disqualification_reason Nullable(String);

-- Add indexes for tournament columns
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_tournament_id tournament_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_participant_type participant_type TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_analytics_daily_runs ADD INDEX IF NOT EXISTS idx_run_order run_order TYPE minmax GRANULARITY 4;