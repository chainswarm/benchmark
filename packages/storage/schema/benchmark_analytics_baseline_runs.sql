CREATE TABLE IF NOT EXISTS benchmark_analytics_baseline_runs (
    run_id UUID DEFAULT generateUUIDv4(),
    baseline_version String,
    test_date Date,
    network String,
    window_days UInt16,
    processing_date Date,

    execution_time_seconds Float64,
    synthetic_patterns_expected UInt32,
    synthetic_patterns_found UInt32,
    synthetic_patterns_recall Float64,

    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (baseline_version, test_date, network);

ALTER TABLE benchmark_analytics_baseline_runs ADD INDEX IF NOT EXISTS idx_run_id run_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_analytics_baseline_runs ADD INDEX IF NOT EXISTS idx_baseline_version baseline_version TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_analytics_baseline_runs ADD INDEX IF NOT EXISTS idx_test_date test_date TYPE minmax GRANULARITY 4;
ALTER TABLE benchmark_analytics_baseline_runs ADD INDEX IF NOT EXISTS idx_network network TYPE set(0) GRANULARITY 4;