"""
Storage module for benchmark pipeline.

Provides schema migration support and database prefix configuration.
All base classes and utilities are imported from chainswarm-core.
"""
from pathlib import Path
from chainswarm_core.db import BaseMigrateSchema

DATABASE_PREFIX = 'benchmark'


class MigrateSchema(BaseMigrateSchema):
    """ClickHouse schema migration manager for benchmark pipeline."""

    core_schemas = [
        "benchmark_miner_registry.sql",
        "benchmark_miner_databases.sql",
        "benchmark_epochs.sql",
        "benchmark_analytics_daily_runs.sql",
        "benchmark_ml_daily_runs.sql",
        "benchmark_analytics_baseline_runs.sql",
        "benchmark_ml_baseline_runs.sql",
        "benchmark_scores.sql",
    ]

    miner_analytics_schemas = [
        "miner_analytics_schema.sql",
    ]

    miner_ml_schemas = [
        "miner_ml_schema.sql",
    ]

    def get_project_schema_dir(self) -> Path:
        return Path(__file__).parent / "schema"

    def run_core_migrations(self) -> None:
        """Run core benchmark schema migrations."""
        self.run_schemas_from_dir(self.core_schemas, self.get_project_schema_dir())

    def run_miner_schema_migrations(self, image_type: str = 'analytics') -> None:
        """Run miner-specific schema migrations based on image type."""
        if image_type == 'analytics':
            self.run_schemas_from_dir(self.miner_analytics_schemas, self.get_project_schema_dir())
        else:
            self.run_schemas_from_dir(self.miner_ml_schemas, self.get_project_schema_dir())


__all__ = ["MigrateSchema", "DATABASE_PREFIX"]