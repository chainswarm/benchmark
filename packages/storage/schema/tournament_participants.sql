CREATE TABLE IF NOT EXISTS tournament_participants (
    tournament_id UUID,
    
    -- Participant identity
    hotkey String,
    participant_type Enum('miner', 'baseline') DEFAULT 'miner',
    
    -- Registration
    registered_at DateTime DEFAULT now(),
    registration_order UInt16,
    
    -- Source
    github_repository String,
    docker_image_tag String,
    miner_database_name String,
    
    -- For baseline participants
    baseline_id Nullable(UUID),
    
    -- Status
    status Enum('registered', 'active', 'completed', 'failed', 'disqualified') DEFAULT 'registered',
    
    -- Disqualification tracking
    is_disqualified Bool DEFAULT false,
    disqualification_reason Nullable(String),
    disqualified_on_day Nullable(UInt8),
    
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tournament_id, registration_order);

ALTER TABLE tournament_participants ADD INDEX IF NOT EXISTS idx_hotkey hotkey TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE tournament_participants ADD INDEX IF NOT EXISTS idx_participant_type participant_type TYPE set(0) GRANULARITY 4;
ALTER TABLE tournament_participants ADD INDEX IF NOT EXISTS idx_status status TYPE set(0) GRANULARITY 4;

-- Add disqualification tracking columns
ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS is_disqualified Bool DEFAULT false;
ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS disqualification_reason Nullable(String);
ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS disqualified_on_day Nullable(UInt8);