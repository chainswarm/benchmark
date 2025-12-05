from datetime import datetime
from typing import List

from clickhouse_connect.driver import Client

from chainswarm_core.db import BaseRepository, row_to_dict
from chainswarm_core.observability import log_errors

from packages.benchmark.models.miner import ImageType, Miner, MinerStatus


class MinerRegistryRepository(BaseRepository):
    
    def __init__(self, client: Client):
        super().__init__(client)

    @classmethod
    def schema(cls) -> str:
        return 'benchmark/benchmark_miner_registry.sql'

    @classmethod
    def table_name(cls) -> str:
        return 'benchmark_miner_registry'

    @log_errors
    def get_active_miners(self, image_type: ImageType) -> List[Miner]:
        query = f"""
        SELECT hotkey, image_type, github_repository, registered_at,
               last_updated_at, status, validation_error
        FROM {self.table_name()} FINAL
        WHERE status = 'active' AND image_type = %(image_type)s
        ORDER BY registered_at
        """
        
        result = self.client.query(query, parameters={'image_type': image_type.value})
        
        miners = []
        for row in result.result_rows:
            data = row_to_dict(row, result.column_names)
            miners.append(Miner(
                hotkey=data['hotkey'],
                image_type=ImageType(data['image_type']),
                github_repository=data['github_repository'],
                registered_at=data['registered_at'],
                last_updated_at=data['last_updated_at'],
                status=MinerStatus(data['status']),
                validation_error=data['validation_error']
            ))
        
        return miners

    @log_errors
    def get_all_miners(self, image_type: ImageType = None) -> List[Miner]:
        if image_type:
            query = f"""
            SELECT hotkey, image_type, github_repository, registered_at,
                   last_updated_at, status, validation_error
            FROM {self.table_name()} FINAL
            WHERE image_type = %(image_type)s
            ORDER BY registered_at
            """
            result = self.client.query(query, parameters={'image_type': image_type.value})
        else:
            query = f"""
            SELECT hotkey, image_type, github_repository, registered_at,
                   last_updated_at, status, validation_error
            FROM {self.table_name()} FINAL
            ORDER BY registered_at
            """
            result = self.client.query(query)
        
        miners = []
        for row in result.result_rows:
            data = row_to_dict(row, result.column_names)
            miners.append(Miner(
                hotkey=data['hotkey'],
                image_type=ImageType(data['image_type']),
                github_repository=data['github_repository'],
                registered_at=data['registered_at'],
                last_updated_at=data['last_updated_at'],
                status=MinerStatus(data['status']),
                validation_error=data['validation_error']
            ))
        
        return miners

    @log_errors
    def get_miner(self, hotkey: str, image_type: ImageType) -> Miner:
        query = f"""
        SELECT hotkey, image_type, github_repository, registered_at,
               last_updated_at, status, validation_error
        FROM {self.table_name()} FINAL
        WHERE hotkey = %(hotkey)s AND image_type = %(image_type)s
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value
        })
        
        if not result.result_rows:
            raise ValueError(f"Miner not found: {hotkey}")
        
        row = result.result_rows[0]
        data = row_to_dict(row, result.column_names)
        return Miner(
            hotkey=data['hotkey'],
            image_type=ImageType(data['image_type']),
            github_repository=data['github_repository'],
            registered_at=data['registered_at'],
            last_updated_at=data['last_updated_at'],
            status=MinerStatus(data['status']),
            validation_error=data['validation_error']
        )

    @log_errors
    def insert_miner(self, miner: Miner) -> None:
        query = f"""
        INSERT INTO {self.table_name()} 
        (hotkey, image_type, github_repository, registered_at, last_updated_at, status, validation_error)
        VALUES (%(hotkey)s, %(image_type)s, %(github_repository)s, %(registered_at)s, 
                %(last_updated_at)s, %(status)s, %(validation_error)s)
        """
        
        self.client.command(query, parameters={
            'hotkey': miner.hotkey,
            'image_type': miner.image_type.value,
            'github_repository': miner.github_repository,
            'registered_at': miner.registered_at,
            'last_updated_at': miner.last_updated_at,
            'status': miner.status.value,
            'validation_error': miner.validation_error
        })

    @log_errors
    def update_miner_status(
        self,
        hotkey: str,
        image_type: ImageType,
        status: MinerStatus,
        validation_error: str = None
    ) -> None:
        now = datetime.now()
        
        query = f"""
        INSERT INTO {self.table_name()}
        (hotkey, image_type, github_repository, registered_at, last_updated_at, status, validation_error)
        SELECT hotkey, image_type, github_repository, registered_at,
               %(last_updated_at)s, %(status)s, %(validation_error)s
        FROM {self.table_name()} FINAL
        WHERE hotkey = %(hotkey)s AND image_type = %(image_type)s
        LIMIT 1
        """
        
        self.client.command(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value,
            'status': status.value,
            'validation_error': validation_error,
            'last_updated_at': now
        })