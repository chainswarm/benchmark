CREATE TABLE IF NOT EXISTS benchmark_miner_registry (
    hotkey String,
    image_type Enum('analytics', 'ml'),
    github_repository String,
    registered_at DateTime DEFAULT now(),
    last_updated_at DateTime DEFAULT now(),
    status Enum('pending', 'active', 'disabled', 'failed') DEFAULT 'pending',
    validation_error Nullable(String)
) ENGINE = ReplacingMergeTree(last_updated_at)
ORDER BY (hotkey, image_type);

ALTER TABLE benchmark_miner_registry ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_miner_registry ADD INDEX IF NOT EXISTS idx_registered_at registered_at TYPE minmax GRANULARITY 4;