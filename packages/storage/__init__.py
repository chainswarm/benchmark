from pathlib import Path
from chainswarm_core.db import BaseMigrateSchema

DATABASE_PREFIX = 'benchmark'


class MigrateSchema(BaseMigrateSchema):

    CORE_SCHEMAS = [
        "benchmark_miner_registry.sql",
        "benchmark_miner_databases.sql",
        "benchmark_epochs.sql",
        "benchmark_analytics_daily_runs.sql",
        "benchmark_ml_daily_runs.sql",
        "benchmark_analytics_baseline_runs.sql",
        "benchmark_ml_baseline_runs.sql",
        "benchmark_scores.sql",
    ]

    TOURNAMENT_SCHEMAS = [
        "baseline_registry.sql",
        "tournament_tournaments.sql",
        "tournament_participants.sql",
        "tournament_results.sql",
    ]

    MINER_ANALYTICS_SCHEMAS = [
        "miner_analytics_schema.sql",
    ]

    MINER_ML_SCHEMAS = [
        "miner_ml_schema.sql",
    ]

    def get_project_schema_dir(self) -> Path:
        return Path(__file__).parent / "schema"

    def run_core_migrations(self) -> None:
        self.run_schemas_from_dir(self.CORE_SCHEMAS, self.get_project_schema_dir())

    def run_tournament_migrations(self) -> None:
        self.run_schemas_from_dir(self.TOURNAMENT_SCHEMAS, self.get_project_schema_dir())

    def run_miner_schema_migrations(self, image_type: str = 'analytics') -> None:
        if image_type == 'analytics':
            self.run_schemas_from_dir(self.MINER_ANALYTICS_SCHEMAS, self.get_project_schema_dir())
        else:
            self.run_schemas_from_dir(self.MINER_ML_SCHEMAS, self.get_project_schema_dir())

    def run_all(self) -> None:
        self.run_core_migrations()
        self.run_tournament_migrations()


__all__ = ["MigrateSchema", "DATABASE_PREFIX"]