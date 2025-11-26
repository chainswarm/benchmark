import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from clickhouse_connect import get_client
from clickhouse_connect.driver import Client

from packages.benchmark.models.epoch import BenchmarkEpoch, EpochStatus
from packages.benchmark.models.miner import ImageType
from packages.storage.repositories.base_repository import BaseRepository
from packages.utils.decorators import log_errors


class BenchmarkEpochRepository(BaseRepository):
    
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
        return 'benchmark/benchmark_epochs.sql'

    @classmethod
    def table_name(cls) -> str:
        return 'benchmark_epochs'

    @log_errors
    def get_epoch_by_id(self, epoch_id: UUID) -> BenchmarkEpoch:
        query = f"""
        SELECT epoch_id, hotkey, image_type, start_date, end_date, status,
               docker_image_tag, miner_database_name, created_at, completed_at
        FROM {self.table_name()}
        WHERE epoch_id = %(epoch_id)s
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={'epoch_id': str(epoch_id)})
        
        if not result.result_rows:
            raise ValueError(f"Epoch not found: {epoch_id}")
        
        row = result.result_rows[0]
        return self._row_to_epoch(row)

    @log_errors
    def get_active_epoch(self, hotkey: str, image_type: ImageType) -> Optional[BenchmarkEpoch]:
        query = f"""
        SELECT epoch_id, hotkey, image_type, start_date, end_date, status,
               docker_image_tag, miner_database_name, created_at, completed_at
        FROM {self.table_name()}
        WHERE hotkey = %(hotkey)s 
          AND image_type = %(image_type)s 
          AND status IN ('pending', 'running')
        ORDER BY start_date DESC
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value
        })
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_epoch(row)

    @log_errors
    def get_epochs_for_miner(self, hotkey: str, image_type: ImageType) -> List[BenchmarkEpoch]:
        query = f"""
        SELECT epoch_id, hotkey, image_type, start_date, end_date, status,
               docker_image_tag, miner_database_name, created_at, completed_at
        FROM {self.table_name()}
        WHERE hotkey = %(hotkey)s AND image_type = %(image_type)s
        ORDER BY start_date DESC
        """
        
        result = self.client.query(query, parameters={
            'hotkey': hotkey,
            'image_type': image_type.value
        })
        
        epochs = []
        for row in result.result_rows:
            epochs.append(self._row_to_epoch(row))
        
        return epochs

    @log_errors
    def insert_epoch(self, epoch: BenchmarkEpoch) -> None:
        query = f"""
        INSERT INTO {self.table_name()} 
        (epoch_id, hotkey, image_type, start_date, end_date, status,
         docker_image_tag, miner_database_name, created_at, completed_at)
        VALUES (%(epoch_id)s, %(hotkey)s, %(image_type)s, %(start_date)s, %(end_date)s,
                %(status)s, %(docker_image_tag)s, %(miner_database_name)s, %(created_at)s, %(completed_at)s)
        """
        
        self.client.command(query, parameters={
            'epoch_id': str(epoch.epoch_id),
            'hotkey': epoch.hotkey,
            'image_type': epoch.image_type.value,
            'start_date': epoch.start_date,
            'end_date': epoch.end_date,
            'status': epoch.status.value,
            'docker_image_tag': epoch.docker_image_tag,
            'miner_database_name': epoch.miner_database_name,
            'created_at': epoch.created_at,
            'completed_at': epoch.completed_at
        })

    @log_errors
    def update_epoch_status(
        self,
        epoch_id: UUID,
        status: str,
        completed_at: datetime = None
    ) -> None:
        epoch = self.get_epoch_by_id(epoch_id)
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (epoch_id, hotkey, image_type, start_date, end_date, status,
         docker_image_tag, miner_database_name, created_at, completed_at)
        VALUES (%(epoch_id)s, %(hotkey)s, %(image_type)s, %(start_date)s, %(end_date)s,
                %(status)s, %(docker_image_tag)s, %(miner_database_name)s, %(created_at)s, %(completed_at)s)
        """
        
        self.client.command(query, parameters={
            'epoch_id': str(epoch_id),
            'hotkey': epoch.hotkey,
            'image_type': epoch.image_type.value,
            'start_date': epoch.start_date,
            'end_date': epoch.end_date,
            'status': status,
            'docker_image_tag': epoch.docker_image_tag,
            'miner_database_name': epoch.miner_database_name,
            'created_at': epoch.created_at,
            'completed_at': completed_at
        })

    def _row_to_epoch(self, row) -> BenchmarkEpoch:
        return BenchmarkEpoch(
            epoch_id=UUID(row[0]) if isinstance(row[0], str) else row[0],
            hotkey=row[1],
            image_type=ImageType(row[2]),
            start_date=row[3],
            end_date=row[4],
            status=EpochStatus(row[5]),
            docker_image_tag=row[6],
            miner_database_name=row[7],
            created_at=row[8],
            completed_at=row[9]
        )