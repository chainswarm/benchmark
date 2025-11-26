CREATE TABLE IF NOT EXISTS miner_output_patterns (
    pattern_id String,
    pattern_type String,
    addresses Array(String),
    transactions Array(String),
    confidence Float64,
    detected_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (pattern_type, detected_at);

ALTER TABLE miner_output_patterns ADD INDEX IF NOT EXISTS idx_pattern_id pattern_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE miner_output_patterns ADD INDEX IF NOT EXISTS idx_pattern_type pattern_type TYPE set(0) GRANULARITY 4;

CREATE TABLE IF NOT EXISTS miner_output_addresses (
    address String,
    risk_label String,
    risk_score Float64,
    pattern_ids Array(String),
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (risk_label, address);

ALTER TABLE miner_output_addresses ADD INDEX IF NOT EXISTS idx_address address TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE miner_output_addresses ADD INDEX IF NOT EXISTS idx_risk_label risk_label TYPE set(0) GRANULARITY 4;
ALTER TABLE miner_output_addresses ADD INDEX IF NOT EXISTS idx_risk_score risk_score TYPE minmax GRANULARITY 4;