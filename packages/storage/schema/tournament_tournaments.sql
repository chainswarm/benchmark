CREATE TABLE IF NOT EXISTS tournament_tournaments (
    tournament_id UUID DEFAULT generateUUIDv4(),
    
    -- Identity
    name String,
    image_type Enum('analytics', 'ml'),
    
    -- Time boundaries (day precision)
    registration_start Date,
    registration_end Date,
    competition_start Date,
    competition_end Date,
    
    -- Configuration
    max_participants UInt16 DEFAULT 10,
    epoch_days UInt8 DEFAULT 7,
    
    -- Test configuration
    test_networks Array(String) DEFAULT ['torus', 'bittensor'],
    test_window_days Array(UInt16) DEFAULT [30, 90],
    
    -- Baseline for this tournament
    baseline_id UUID,
    
    -- Status tracking
    status Enum('draft', 'registration', 'in_progress', 'scoring', 'completed', 'cancelled') DEFAULT 'draft',
    current_day UInt8 DEFAULT 0,
    
    -- Results
    winner_hotkey Nullable(String),
    baseline_beaten Bool DEFAULT false,
    
    created_at DateTime DEFAULT now(),
    completed_at Nullable(DateTime)
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (tournament_id);

ALTER TABLE tournament_tournaments ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;
ALTER TABLE tournament_tournaments ADD INDEX IF NOT EXISTS idx_image_type image_type TYPE set(0) GRANULARITY 4;
ALTER TABLE tournament_tournaments ADD INDEX IF NOT EXISTS idx_competition_start competition_start TYPE minmax GRANULARITY 4;