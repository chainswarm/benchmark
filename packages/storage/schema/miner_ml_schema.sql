CREATE TABLE IF NOT EXISTS miner_risk_scores (
    address String,
    risk_score Float64,
    model_version String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (address);

ALTER TABLE miner_risk_scores ADD INDEX IF NOT EXISTS idx_address address TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE miner_risk_scores ADD INDEX IF NOT EXISTS idx_risk_score risk_score TYPE minmax GRANULARITY 4;
ALTER TABLE miner_risk_scores ADD INDEX IF NOT EXISTS idx_model_version model_version TYPE bloom_filter(0.01) GRANULARITY 4;