"""
Pytest configuration for integration tests.

Provides shared ClickHouse client and database fixtures
for all integration tests that require database access.
"""

import pytest
from clickhouse_connect import get_client
from packages.storage.repositories import MigrateSchema

# Test parameters
TEST_NETWORK = "torus"
TEST_PROCESSING_DATE = "2025-11-20"
TEST_WINDOW_DAYS = 300


@pytest.fixture(scope="session")
def test_clickhouse_client():
    """
    Shared ClickHouse client for all integration tests.

    Connects to test ClickHouse instance from docker-compose.
    """
    client = get_client(
        host='localhost',
        port=8323,
        username='test',
        password='test',
        database='test'
    )

    yield client
    client.close()


@pytest.fixture(scope="session")
def setup_test_schema(test_clickhouse_client):
    """
    Initialize test database schema.

    Runs migrations to create all required tables.
    """
    migrator = MigrateSchema(test_clickhouse_client)
    migrator.run_core_migrations()
    migrator.run_analyzer_migrations()
    yield
    # Cleanup after all tests (optional)


@pytest.fixture(scope="function")
def clean_pattern_tables(test_clickhouse_client):
    """
    Clean pattern tables before each test.

    Ensures test isolation by truncating all pattern tables.
    """
    tables = [
        'analyzers_patterns_cycle',
        'analyzers_patterns_layering',
        'analyzers_patterns_network',
        'analyzers_patterns_proximity',
        'analyzers_patterns_motif',
        'analyzers_patterns_threshold',
        'analyzers_patterns_burst'
    ]

    for table in tables:
        try:
            test_clickhouse_client.command(f"TRUNCATE TABLE IF EXISTS {table}")
        except Exception as e:
            # Table might not exist yet
            pass

    yield


@pytest.fixture(scope="session")
def test_data_context():
    """Provide test data context."""
    return {
        'network': TEST_NETWORK,
        'processing_date': TEST_PROCESSING_DATE,
        'window_days': TEST_WINDOW_DAYS
    }