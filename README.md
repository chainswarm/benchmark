# Chain Synthetics

[![CI](https://github.com/chainswarm/chain-synthetics/actions/workflows/ci.yml/badge.svg)](https://github.com/chainswarm/chain-synthetics/actions/workflows/ci.yml)
[![Release](https://github.com/chainswarm/chain-synthetics/actions/workflows/image.yml/badge.svg)](https://github.com/chainswarm/chain-synthetics/actions/workflows/image.yml)

**Synthetic blockchain data generation for validator testing and miner evaluation.**

Chain Synthetics is a "Red Team" engine that generates realistic synthetic blockchain transaction patterns (hacks, money laundering, fake exchanges) and injects them into background data. It serves as the shared testing framework for validating miners across Analytics and Machine Learning Subnet tournaments.

## 🎯 Purpose

The framework generates transactional graph patterns that are statistically indistinguishable from real blockchain data when merged with `core_transfers`. This enables objective evaluation of miner capabilities:

### 1. Analysis Tournament (Pattern Detection)
- **Goal:** Verify miners can find structural anomalies
- **Method:** Inject synthetic patterns (see Pattern Support Matrix below)
- **Scoring:** Does the miner's output graph contain the injected subgraph IDs?

### 2. ML Tournament (Risk Scoring)
- **Goal:** Verify miners can accurately assess risk
- **Method:** Inject known "Bad Patterns" (Target=1) and "Benign Patterns" like Fake Exchanges (Target=0)
- **Scoring:** AUC-ROC on the ground truth labels

## 📊 Pattern Support Matrix

### Implemented Generators (18 Total)

#### 🔴 Money Laundering & Structuring

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Peel Chain** | `recursive_linear` | Progressive peeling of funds to different addresses |
| **Smurfing Network** | `smurfing_network` | Large amounts broken into many sub-threshold transactions |
| **Threshold Evasion** | `threshold_evasion` | Transactions structured below reporting limits ($10K CTR, €15K EU) |
| **Layering Path** | `linear_path` | Deep linear hops to distance funds from source |
| **Mixer/Hourglass** | `hourglass` | Many→Accumulator→Many (tumbler/mixing pattern) |

#### 🔴 Network Topology Patterns

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Fan-Out** | `star_outbound` | One-to-many distribution (exchange withdrawals, airdrops) |
| **Fan-In** | `star_inbound` | Many-to-one collection (aggregation before exit) |
| **Cycle** | `cycle` | Circular transactions returning to origin |
| **Temporal Burst** | `temporal_burst` | High-frequency transactions in tight block windows |

#### 🔴 Market Manipulation & Fraud

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Wash Trading** | `wash_trading` | Self-referential trading between controlled wallets |
| **Sybil Network** | `sybil_network` | Coordinated fake identities for airdrop farming |
| **Rug Pull** | `rug_pull` | Exit scam with rapid or gradual liquidity drain |
| **Nested Services** | `nested_services` | Unlicensed exchange operating through licensed exchange |

#### 🟡 Behavioral Anomalies

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Dormant Activation** | `dormant_activation` | Long-inactive wallets suddenly becoming active |

#### 🟠 Proximity & Relational Risk

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Proximity Risk** | `proximity_risk` | Hop-distance exposure to flagged addresses (sanctions, exploits, mixers, darknet). Uses direction-agnostic BFS to calculate minimum graph distance. Generates address labels for flagged addresses. |

####  Benign Patterns (False Positive Testing)

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Centralized Service** | `centralized_service` | Exchange-like hub pattern (legitimate baseline) |

#### ⚙️ Composite & Custom

| Generator | Template Type | Description |
|-----------|--------------|-------------|
| **Blueprint** | `blueprint` | Custom graph replay from JSON definitions |
| **Sequence** | `sequence` | Multi-stage composite attacks (chain multiple patterns) |

### Detection PatternTypes (defined in `packages/storage/constants.py`)

| PatternType | Generator Support | Detection Method | Status |
|-------------|-------------------|------------------|--------|
| `CYCLE` | ✅ `cycle`, `wash_trading` | `CYCLE_DETECTION` | ✅ Implemented |
| `LAYERING_PATH` | ✅ `linear_path`, `recursive_linear` | `PATH_ANALYSIS` | ✅ Implemented |
| `MOTIF_FANOUT` | ✅ `star_outbound`, `temporal_burst` | `MOTIF_DETECTION` | ✅ Implemented |
| `MOTIF_FANIN` | ✅ `star_inbound`, `hourglass` | `MOTIF_DETECTION` | ✅ Implemented |
| `TEMPORAL_BURST` | ✅ `temporal_burst` | `TEMPORAL_ANALYSIS` | ✅ Implemented |
| `SMURFING_NETWORK` | ✅ `smurfing_network` | `NETWORK_ANALYSIS` | ✅ Implemented |
| `THRESHOLD_EVASION` | ✅ `threshold_evasion` | `PATH_ANALYSIS` | ✅ Implemented |
| `WASH_TRADING` | ✅ `wash_trading` | `CYCLE_DETECTION` | ✅ Implemented |
| `SYBIL_NETWORK` | ✅ `sybil_network` | `NETWORK_ANALYSIS` | ✅ Implemented |
| `NESTED_SERVICES` | ✅ `nested_services` | `NETWORK_ANALYSIS` | ✅ Implemented |
| `RUG_PULL` | ✅ `rug_pull` | `TEMPORAL_ANALYSIS` | ✅ Implemented |
| `DORMANT_ACTIVATION` | ✅ `dormant_activation` | `TEMPORAL_ANALYSIS` | ✅ Implemented |
| `PROXIMITY_RISK` | ✅ `proximity_risk` | `PROXIMITY_ANALYSIS` | ✅ Implemented |

### Potential Future Patterns

| Pattern | Description | Complexity | Use Case |
|---------|-------------|------------|----------|
| **Mixing/Tornado** | CoinJoin, privacy protocol patterns | High | Privacy abuse |
| **Chain Hopping** | Cross-chain bridge exploitation | High | Cross-chain laundering |
| **Flash Loan Attack** | Borrow→exploit→repay in single block | High | DeFi exploits |
| **Sandwich Attack** | Front/back-running victim transactions | High | MEV exploitation |
| **Dusting Attack** | Tiny amounts to many addresses | Low | Address tracking |

## 📦 Package Structure

```
packages/
├── evaluation/            # Core evaluation logic
│   ├── risk_evaluator.py  # Orchestrator and scoring
│   └── synthetic/         # Synthetic data generation
│       ├── generators.py  # Topology creation (Peel, FanOut, Blueprint)
│       ├── injector.py    # Deep merging with background data
│       └── templates/     # JSON attack definitions
│
├── ingestion/             # Data ingestion pipeline
│   ├── service.py         # Ingestion orchestrator
│   ├── extractors/        # Data source connectors
│   │   ├── clickhouse_extractor.py
│   │   ├── http_extractor.py
│   │   └── s3_extractor.py
│   └── loaders/           # Data loaders
│       └── parquet_loader.py
│
├── jobs/                  # Background task processing
│   ├── celery_app.py      # Celery configuration
│   ├── beat_schedule.json # Scheduled tasks
│   └── tasks/             # Task implementations
│       ├── daily_synthetics_pipeline_task.py
│       ├── export_batch_task.py
│       ├── ingest_batch_task.py
│       ├── initialize_synthetics_task.py
│       └── produce_synthetics_task.py
│
├── storage/               # Data persistence layer
│   ├── constants.py       # PatternTypes, RiskLevels, DetectionMethods
│   ├── repositories/      # ClickHouse repositories
│   │   ├── transfer_repository.py
│   │   ├── ground_truth_repository.py
│   │   ├── synthetic_transfer_repository.py
│   │   └── address_label_repository.py  # NEW: Proximity risk labels
│   └── schema/            # Database schemas
│       ├── core_transfers.sql
│       ├── synthetics_transfers.sql
│       ├── synthetics_ground_truth.sql  # Extended with hop_distance
│       ├── merged_transfers_view.sql
│       ├── core_address_labels_referential.sql  # NEW
│       ├── synthetics_address_labels.sql  # NEW
│       └── core_address_labels_view.sql  # NEW: Unified VIEW
│
└── utils/                 # Shared utilities
    ├── crypto_utils.py    # Multi-chain address generation
    ├── pattern_utils.py   # Pattern hashing and ID generation
    ├── decimal_utils.py   # Precision handling
    └── generators/        # Chain-specific generators
        ├── evm.py         # Ethereum/EVM addresses
        ├── substrate.py   # Polkadot/Torus/Bittensor
        └── bitcoin.py     # Bitcoin UTXO
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- ClickHouse database
- Redis (for Celery tasks)

### Installation

```bash
# Clone the repository
git clone https://github.com/chainswarm/chain-synthetics.git
cd chain-synthetics

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### Running the Daily Pipeline

```bash
# Run for a specific network, date, and window
python scripts/tasks/run_daily_chain_synthetics_pipeline.py \
  --network polkadot \
  --processing-date 2025-01-15 \
  --window-days 30

# The pipeline will:
# 1. Initialize schema
# 2. Truncate all tables (fresh run)
# 3. Ingest data from source
# 4. Generate synthetic patterns
# 5. Log computation audit
# 6. Export to S3
```

### Running with Docker

```bash
cd ops
docker-compose up -d
```

## 🔧 Configuration

Environment variables (`.env`):

```bash
# ClickHouse Configuration
CLICKHOUSE_HOST=localhost
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_NATIVE_PORT=9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=synthetics

# Redis Configuration (for Celery)
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO
LOGS_DIR=/var/log/synthetics
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=packages --cov-report=html
```

## 📋 Development

### Adding New Pattern Types

1. Define the pattern topology in [`packages/evaluation/synthetic/generators.py`](packages/evaluation/synthetic/generators.py)
2. Add template definitions to [`packages/evaluation/synthetic/templates/`](packages/evaluation/synthetic/templates/)
3. Update the injector logic in [`packages/evaluation/synthetic/injector.py`](packages/evaluation/synthetic/injector.py)
4. Add the PatternType constant to [`packages/storage/constants.py`](packages/storage/constants.py)

### Adding New Chain Support

1. Create a generator in [`packages/utils/generators/`](packages/utils/generators/)
2. Register the chain type in [`packages/utils/crypto_utils.py`](packages/utils/crypto_utils.py)

## 📝 Documentation

- [Pattern Generators Roadmap](docs/PATTERN_GENERATORS_ROADMAP.md) - Implementation status of all pattern generators
- [Template Configuration Guide](packages/evaluation/synthetic/templates/README.md) - Comprehensive guide to configuring pattern templates
- [Synthetics Remediation Plan](docs/SYNTHETICS_REMEDIATION_PLAN.md) - Technical roadmap and implementation details
- [Export Compatibility Plan](docs/EXPORT_COMPATIBILITY_PLAN.md) - Data export format specifications
- [Proximity Risk Address Labels Plan](docs/PROXIMITY_RISK_ADDRESS_LABELS_PLAN.md) - Address labels integration for hop-distance analysis

## 📓 Jupyter Notebooks

Interactive notebooks for pattern validation and visualization are available in [`notebooks/synthetics/`](notebooks/synthetics/):

| Notebook | Purpose |
|----------|---------|
| [01_pattern_overview.ipynb](notebooks/synthetics/01_pattern_overview.ipynb) | Pattern summary, statistics, role distribution |
| [02_pattern_validation.ipynb](notebooks/synthetics/02_pattern_validation.ipynb) | Structural validation, topology checks |
| [03_pattern_visualization.ipynb](notebooks/synthetics/03_pattern_visualization.ipynb) | Interactive PyVis graph visualization |

```bash
# Run notebooks
jupyter lab notebooks/synthetics/
```

## 📤 S3 Export

The daily pipeline exports all data to S3 in Parquet format:

```
s3://bucket/snapshots/{network}/{processing_date}/{window_days}/
├── transfers.parquet         # Merged transfers (core + synthetic)
├── address_labels.parquet    # Address labels (core + synthetic)
├── ground_truth.parquet      # Ground truth for evaluation
├── assets.parquet            # Asset metadata
├── asset_prices.parquet      # Historical prices
└── META.json                 # Batch metadata with counts and hashes
```

### Exported Files

| File | Source | Description |
|------|--------|-------------|
| `transfers.parquet` | `core_transfers` VIEW | Real + synthetic transfers unified |
| `address_labels.parquet` | `core_address_labels` VIEW | Real + synthetic flagged addresses |
| `ground_truth.parquet` | `synthetics_ground_truth` | Pattern labels for evaluation |
| `assets.parquet` | `core_assets` | Asset metadata |
| `asset_prices.parquet` | `core_asset_prices` | Historical price data |

### S3 Configuration

```bash
# .env configuration
SYNTHETICS_S3_ENABLED=true
SYNTHETICS_S3_ENDPOINT=https://s3.amazonaws.com
SYNTHETICS_S3_BUCKET=your-bucket
SYNTHETICS_S3_ACCESS_KEY=...
SYNTHETICS_S3_SECRET_KEY=...
SYNTHETICS_S3_REGION=us-east-1
```

## 🏷️ Address Labels (Proximity Risk)

The proximity risk pattern uses **Address Labels** to identify flagged addresses. Labels follow the referential pattern:

```
core_address_labels_referential  ──┐
                                   ├──> core_address_labels VIEW
synthetics_address_labels        ──┘
```

### Supported Flag Types

| Flag Type | Description | Risk Level |
|-----------|-------------|------------|
| `sanctions` | OFAC sanctioned entities | 10 (Critical) |
| `exploit` | Known exploit addresses | 10 (Critical) |
| `mixer` | Mixing service addresses | 8 (High) |
| `darknet` | Darknet market addresses | 9 (Very High) |

### Hop Distance Calculation

Ground truth includes hop distance for each address:
- `hop_distance = 0`: Flagged address itself
- `hop_distance = 1`: Direct counterparty (immediate neighbor)
- `hop_distance = 2+`: Indirect exposure

Hop distances are calculated using **direction-agnostic BFS** - the minimum graph distance regardless of edge direction.

## 🔄 CI/CD

- **CI Pipeline**: Runs on push to `main`, `develop`, and `feature/**` branches
- **Release Pipeline**: Manual trigger to create tags and publish Docker images to GHCR

## 📄 License

[Add your license here]

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request