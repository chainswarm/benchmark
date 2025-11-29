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


def create_database(connection_params):
    client = get_client(
        host=connection_params['host'],
        port=int(connection_params['port']),
        username=connection_params['user'],
        password=connection_params['password'],
        database='default',
        settings={
            'enable_http_compression': 1,
            'send_progress_in_http_headers': 0,
            'http_headers_progress_interval_ms': 1000,
            'http_zlib_compression_level': 3,
            'max_execution_time': connection_params.get('max_execution_time', 3600),
            "max_query_size": connection_params.get('max_query_size', 5000000)
        }
    )

    client.command(f"CREATE DATABASE IF NOT EXISTS {connection_params['database']}")

def get_connection_params(database: str = 'default'):
    connection_params = {
        "host": os.getenv(f"CLICKHOUSE_HOST", "localhost"),
        "port": os.getenv(f"CLICKHOUSE_PORT", "8823"),
        "database": database,
        "user": os.getenv(f"CLICKHOUSE_USER", "default"),
        "password": os.getenv(f"CLICKHOUSE_PASSWORD", f"password1234"),
        "max_execution_time": int(os.getenv(f"CLICKHOUSE_MAX_EXECUTION_TIME", "1800")),
        "max_query_size": int(os.getenv(f"CLICKHOUSE_MAX_QUERY_SIZE", "5000000")),
    }

    return connection_params

def truncate_table(client: Client, table_name) -> None:
    client.command(f"TRUNCATE TABLE IF EXISTS {table_name}")

def apply_schema(client: Client, schema: str, replacements: dict = None):
    def _split_clickhouse_sql(sql_text: str) -> Iterable[str]:
        cleaned = io.StringIO()
        for line in sql_text.splitlines():
            if line.strip().startswith("--"):
                continue
            parts = line.split("--", 1)
            cleaned.write(parts[0] + "\n")

        buf = []
        for ch in cleaned.getvalue():
            if ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    yield stmt
                buf = []
            else:
                buf.append(ch)

        tail = "".join(buf).strip()
        if tail:
            yield tail

    schema_path = Path(__file__).resolve().parents[1] / "schema" / schema
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"schema {schema} does not exist")

    raw = path.read_text(encoding="utf-8")

    statements = list(_split_clickhouse_sql(raw))
    if not statements:
        return

    for i, stmt in enumerate(statements, 1):
        client.command(stmt)

class ClientFactory:
    client: Client = None

    def __init__(self, connection_params) -> None:
        self.connection_params = connection_params

    def _get_client(self) -> Client:
        self.client = get_client(
            host=self.connection_params['host'],
            port=int(self.connection_params['port']),
            username=self.connection_params['user'],
            password=self.connection_params['password'],
            database=self.connection_params['database'],
            settings={
                'output_format_parquet_compression_method': 'zstd',
                'async_insert': 0,
                'wait_for_async_insert': 1,
                'max_execution_time': 300,
                'max_execution_time': self.connection_params.get('max_execution_time', 3600),
                "max_query_size": self.connection_params.get('max_query_size', 5000000)
            }

        )
        return self.client

    def _get_client_default_database(self) -> Client:
        client = get_client(
            host=self.connection_params['host'],
            port=int(self.connection_params['port']),
            username=self.connection_params['user'],
            password=self.connection_params['password'],
            database='default',
            settings={
                'output_format_parquet_compression_method': 'zstd',
                'max_execution_time': self.connection_params.get('max_execution_time', 3600),
                "max_query_size": self.connection_params.get('max_query_size', 5000000),

                'enable_http_compression': 1,
                'send_progress_in_http_headers': 0,
                'http_headers_progress_interval_ms': 1000,
                'http_zlib_compression_level': 3,
            },
            client_query_params={
                'default_format': 'JSON',
                'result_format': 'JSON'
            }
        )
        return client

    @contextmanager
    def client_context(self) -> Iterator[Client]:
        client = self._get_client()
        try:
            yield client
        except ClickHouseError as e:
            import traceback
            logger.error(
                "ClickHouse error",
                error = e,
                traceback = traceback.format_exc(),
            )
            raise
        finally:
            if client:
                client.close()

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
