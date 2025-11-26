import os
from datetime import datetime
from typing import List

from clickhouse_connect import get_client
from clickhouse_connect.driver import Client

from packages.benchmark.models.miner import ImageType, MinerDatabase
from packages.storage.repositories.base_repository import BaseRepository
from packages.utils.decorators import log_errors


class MinerDatabaseRepository(BaseRepository):
    
    def __init__(self, client: Client = None):
        if client is None:
            client = get_client(
                host=os.environ['VALIDATOR_CH_HOST'],
                port=int(os.environ['VALIDATOR_CH_PORT']),
                database='default'
            )
        super().__init__(client)

    @classmethod
    def schema(cls) -> str:
        return 'benchmark/benchmark_miner_databases.sql'

    @classmethod
    def table_name(cls) -> str:
        return 'benchmark_miner_databases'

    @log_errors
    def get_database(self, hotkey: str, image_type: ImageType) -> MinerDatabase:
        query = f"""
        SELECT hotkey, image_type, database_name, created_at, last_used_at, status
        FROM {self.table_name()}
        WHERE hotkey = %(hotkey)s AND image_type = %(image_type)s
        ORDER BY last_used_at DESC
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value
        })
        
        if not result.result_rows:
            raise ValueError(f"Database not found for miner: {hotkey}")
        
        row = result.result_rows[0]
        return MinerDatabase(
            hotkey=row[0],
            image_type=ImageType(row[1]),
            database_name=row[2],
            created_at=row[3],
            last_used_at=row[4],
            status=row[5]
        )

    @log_errors
    def get_active_databases(self) -> List[MinerDatabase]:
        query = f"""
        SELECT hotkey, image_type, database_name, created_at, last_used_at, status
        FROM {self.table_name()}
        WHERE status = 'active'
        ORDER BY last_used_at DESC
        """
        
        result = self.client.query(query)
        
        databases = []
        for row in result.result_rows:
            databases.append(MinerDatabase(
                hotkey=row[0],
                image_type=ImageType(row[1]),
                database_name=row[2],
                created_at=row[3],
                last_used_at=row[4],
                status=row[5]
            ))
        
        return databases

    @log_errors
    def insert_database(
        self,
        hotkey: str,
        image_type: ImageType,
        database_name: str
    ) -> None:
        now = datetime.now()
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (hotkey, image_type, database_name, created_at, last_used_at, status)
        VALUES (%(hotkey)s, %(image_type)s, %(database_name)s, %(created_at)s, %(last_used_at)s, 'active')
        """
        
        self.client.command(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value,
            'database_name': database_name,
            'created_at': now,
            'last_used_at': now
        })

    @log_errors
    def update_database_status(
        self,
        hotkey: str,
        image_type: ImageType,
        status: str
    ) -> None:
        now = datetime.now()
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (hotkey, image_type, database_name, created_at, last_used_at, status)
        SELECT hotkey, image_type, database_name, created_at, %(last_used_at)s, %(status)s
        FROM {self.table_name()}
        WHERE hotkey = %(hotkey)s AND image_type = %(image_type)s
        ORDER BY last_used_at DESC
        LIMIT 1
        """
        
        self.client.command(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value,
            'status': status,
            'last_used_at': now
        })

    @log_errors
    def update_last_used(self, hotkey: str, image_type: ImageType) -> None:
        now = datetime.now()
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (hotkey, image_type, database_name, created_at, last_used_at, status)
        SELECT hotkey, image_type, database_name, created_at, %(last_used_at)s, status
        FROM {self.table_name()}
        WHERE hotkey = %(hotkey)s AND image_type = %(image_type)s
        ORDER BY last_used_at DESC
        LIMIT 1
        """
        
        self.client.command(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value,
            'last_used_at': now
        })