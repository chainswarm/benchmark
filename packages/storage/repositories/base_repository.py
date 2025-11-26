from abc import ABC, abstractmethod
from datetime import datetime
import clickhouse_connect
import time

class BaseRepository(ABC):
    def __init__(self, client: clickhouse_connect.driver.Client, partition_id: int = None):
        self.client = client
        self.partition_id = partition_id

    def _generate_version(self) -> int:
        base_version = int(time.time() * 1000000)
        if self.partition_id is not None:
            return base_version + self.partition_id
        return base_version

    @classmethod
    def schema(cls) -> str:
        """Return the schema file name for this repository"""
        pass
    
    @classmethod
    def table_name(cls) -> str:
        """Return the table name for this repository"""
        pass