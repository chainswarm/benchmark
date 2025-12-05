import io
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Iterable
from clickhouse_connect import get_client
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.exceptions import ClickHouseError
from loguru import logger
from packages.storage.repositories.base_repository import BaseRepository


class MigrateSchema:
    def __init__(self, client: Client):
        self.client = client

    def run_core_migrations(self):
        benchmark_schemas = [
            "benchmark_miner_registry.sql",
            "benchmark_miner_databases.sql",
            "benchmark_epochs.sql",
            "benchmark_analytics_daily_runs.sql",
            "benchmark_ml_daily_runs.sql",
            "benchmark_analytics_baseline_runs.sql",
            "benchmark_ml_baseline_runs.sql",
            "benchmark_scores.sql",
        ]

        for schema_file in benchmark_schemas:
            try:
                apply_schema(self.client, schema_file)
                logger.info(f"Executed benchmark schema {schema_file}")
            except FileNotFoundError:
                logger.warning(f"Benchmark schema {schema_file} not found, skipping")

    def run_miner_schema_migrations(self, image_type: str = 'analytics'):
        if image_type == 'analytics':
            schema_file = "miner_analytics_schema.sql"
        else:
            schema_file = "miner_ml_schema.sql"
        
        try:
            apply_schema(self.client, schema_file)
            logger.info(f"Executed miner schema {schema_file}")
        except FileNotFoundError:
            logger.warning(f"Miner schema {schema_file} not found, skipping")
