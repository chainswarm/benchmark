CREATE TABLE IF NOT EXISTS benchmark_scores (
    epoch_id UUID,
    hotkey String,
    image_type Enum('analytics', 'ml'),

    data_correctness_all_days Bool,

    pattern_accuracy_score Float64,
    data_correctness_score Float64,
    performance_score Float64,

    final_score Float64,
    rank UInt32,

    baseline_comparison_ratio Float64,

    all_runs_within_time_limit Bool,
    average_execution_time_seconds Float64,

    calculated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(calculated_at)
ORDER BY (hotkey, image_type);

ALTER TABLE benchmark_scores ADD INDEX IF NOT EXISTS idx_epoch_id epoch_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_scores ADD INDEX IF NOT EXISTS idx_image_type image_type TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_scores ADD INDEX IF NOT EXISTS idx_final_score final_score TYPE minmax GRANULARITY 4;
ALTER TABLE benchmark_scores ADD INDEX IF NOT EXISTS idx_rank rank TYPE minmax GRANULARITY 4;
ALTER TABLE benchmark_scores ADD INDEX IF NOT EXISTS idx_calculated_at calculated_at TYPE minmax GRANULARITY 4;