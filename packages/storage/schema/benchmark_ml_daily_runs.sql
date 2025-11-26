CREATE TABLE IF NOT EXISTS benchmark_ml_daily_runs (
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

    auc_roc Float64,
    precision_at_recall_80 Float64,

    all_addresses_exist Bool,
    data_correctness_passed Bool,

    status Enum('pending', 'running', 'completed', 'timeout', 'failed') DEFAULT 'pending',
    error_message Nullable(String),

    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (epoch_id, test_date, network);

ALTER TABLE benchmark_ml_daily_runs ADD INDEX IF NOT EXISTS idx_run_id run_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_ml_daily_runs ADD INDEX IF NOT EXISTS idx_hotkey hotkey TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_ml_daily_runs ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_ml_daily_runs ADD INDEX IF NOT EXISTS idx_network network TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_ml_daily_runs ADD INDEX IF NOT EXISTS idx_test_date test_date TYPE minmax GRANULARITY 4;
ALTER TABLE benchmark_ml_daily_runs ADD INDEX IF NOT EXISTS idx_data_correctness data_correctness_passed TYPE set(0) GRANULARITY 4;