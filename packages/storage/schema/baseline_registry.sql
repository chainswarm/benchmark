CREATE TABLE IF NOT EXISTS baseline_registry (
    baseline_id UUID DEFAULT generateUUIDv4(),
    image_type Enum('analytics', 'ml'),
    
    -- Version tracking
    version String,  -- e.g., "v1.0.0", "v1.1.0"
    
    -- Source code location
    github_repository String,  -- Fork location: "chainswarm/baseline-analytics"
    commit_hash String,        -- Pinned commit
    
    -- Docker image
    docker_image_tag String,   -- e.g., "baseline_analytics_v1.0.0"
    
    -- Origin tracking (who created this baseline)
    originated_from_tournament_id Nullable(UUID),  -- Tournament where winner was crowned
    originated_from_hotkey Nullable(String),       -- Original miner hotkey
    
    -- Status
    status Enum('building', 'active', 'deprecated', 'failed') DEFAULT 'building',
    
    -- Timestamps
    created_at DateTime DEFAULT now(),
    activated_at Nullable(DateTime),
    deprecated_at Nullable(DateTime)
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (image_type, version);

ALTER TABLE baseline_registry ADD INDEX IF NOT EXISTS idx_baseline_id baseline_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE baseline_registry ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;
ALTER TABLE baseline_registry ADD INDEX IF NOT EXISTS idx_image_type image_type TYPE set(0) GRANULARITY 4;