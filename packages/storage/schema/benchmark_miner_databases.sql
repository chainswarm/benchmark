CREATE TABLE IF NOT EXISTS benchmark_miner_databases (
    hotkey String,
    image_type Enum('analytics', 'ml'),
    database_name String,
    created_at DateTime DEFAULT now(),
    last_used_at DateTime DEFAULT now(),
    status Enum('active', 'archived', 'deleted') DEFAULT 'active'
) ENGINE = ReplacingMergeTree(last_used_at)
ORDER BY (hotkey, image_type);

ALTER TABLE benchmark_miner_databases ADD INDEX IF NOT EXISTS idx_database_name database_name TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_miner_databases ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;