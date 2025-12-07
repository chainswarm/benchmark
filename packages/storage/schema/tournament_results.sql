CREATE TABLE IF NOT EXISTS tournament_results (
    tournament_id UUID,
    hotkey String,
    participant_type Enum('miner', 'baseline'),
    
    -- Aggregated scores
    pattern_accuracy_score Float64,
    data_correctness_score Float64,
    performance_score Float64,
    final_score Float64,
    
    -- Validation status
    data_correctness_all_days Bool,
    all_runs_within_time_limit Bool,
    days_completed UInt8,
    total_runs_completed UInt16,
    
    -- Performance metrics
    average_execution_time_seconds Float64,
    baseline_comparison_ratio Float64,
    
    -- Ranking
    rank UInt16,
    is_winner Bool DEFAULT false,
    beat_baseline Bool DEFAULT false,
    miners_beaten UInt16 DEFAULT 0,
    
    calculated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(calculated_at)
ORDER BY (tournament_id, rank);

ALTER TABLE tournament_results ADD INDEX IF NOT EXISTS idx_hotkey hotkey TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE tournament_results ADD INDEX IF NOT EXISTS idx_final_score final_score TYPE minmax GRANULARITY 4;
ALTER TABLE tournament_results ADD INDEX IF NOT EXISTS idx_is_winner is_winner TYPE set(0) GRANULARITY 4;
ALTER TABLE tournament_results ADD INDEX IF NOT EXISTS idx_participant_type participant_type TYPE set(0) GRANULARITY 4;