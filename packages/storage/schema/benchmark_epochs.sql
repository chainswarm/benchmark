CREATE TABLE IF NOT EXISTS benchmark_epochs (
    epoch_id UUID DEFAULT generateUUIDv4(),
    hotkey String,
    image_type Enum('analytics', 'ml'),
    start_date Date,
    end_date Date,
    status Enum('pending', 'running', 'completed', 'failed') DEFAULT 'pending',
    docker_image_tag String,
    miner_database_name String,
    created_at DateTime DEFAULT now(),
    completed_at Nullable(DateTime),
    
    -- Tournament tracking (optional - null for standalone benchmarks)
    tournament_id Nullable(UUID)
) ENGINE = MergeTree()
ORDER BY (hotkey, start_date);

ALTER TABLE benchmark_epochs ADD INDEX IF NOT EXISTS idx_epoch_id epoch_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE benchmark_epochs ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_epochs ADD INDEX IF NOT EXISTS idx_image_type image_type TYPE set(0) GRANULARITY 4;
ALTER TABLE benchmark_epochs ADD INDEX IF NOT EXISTS idx_start_date start_date TYPE minmax GRANULARITY 4;
ALTER TABLE benchmark_epochs ADD INDEX IF NOT EXISTS idx_end_date end_date TYPE minmax GRANULARITY 4;

-- Add tournament_id column for linking epochs to tournaments
ALTER TABLE benchmark_epochs ADD COLUMN IF NOT EXISTS tournament_id Nullable(UUID);
ALTER TABLE benchmark_epochs ADD INDEX IF NOT EXISTS idx_tournament_id tournament_id TYPE bloom_filter(0.01) GRANULARITY 4;