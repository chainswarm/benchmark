from datetime import datetime
from typing import Optional
from uuid import UUID

from clickhouse_connect.driver import Client

from chainswarm_core.db import BaseRepository, row_to_dict
from chainswarm_core.observability import log_errors

from packages.benchmark.models.baseline import Baseline, BaselineStatus
from packages.benchmark.models.miner import ImageType


class BaselineRepository(BaseRepository):
    
    def __init__(self, client: Client):
        super().__init__(client)

    @classmethod
    def schema(cls) -> str:
        return 'benchmark/baseline_registry.sql'

    @classmethod
    def table_name(cls) -> str:
        return 'baseline_registry'

    @log_errors
    def get_active_baseline(self, image_type: ImageType) -> Optional[Baseline]:
        """Get the currently active baseline for an image type."""
        query = f"""
        SELECT baseline_id, image_type, version, github_repository, commit_hash,
               docker_image_tag, originated_from_tournament_id, originated_from_hotkey,
               status, created_at, activated_at, deprecated_at
        FROM {self.table_name()} FINAL
        WHERE image_type = %(image_type)s AND status = 'active'
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={'image_type': image_type.value})
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_baseline(row, result.column_names)

    @log_errors
    def get_baseline_by_id(self, baseline_id: UUID) -> Optional[Baseline]:
        """Get baseline by ID."""
        query = f"""
        SELECT baseline_id, image_type, version, github_repository, commit_hash,
               docker_image_tag, originated_from_tournament_id, originated_from_hotkey,
               status, created_at, activated_at, deprecated_at
        FROM {self.table_name()} FINAL
        WHERE baseline_id = %(baseline_id)s
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={'baseline_id': str(baseline_id)})
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_baseline(row, result.column_names)

    @log_errors
    def insert_baseline(self, baseline: Baseline) -> None:
        """Insert a new baseline."""
        query = f"""
        INSERT INTO {self.table_name()} 
        (baseline_id, image_type, version, github_repository, commit_hash,
         docker_image_tag, originated_from_tournament_id, originated_from_hotkey,
         status, created_at, activated_at, deprecated_at)
        VALUES (%(baseline_id)s, %(image_type)s, %(version)s, %(github_repository)s,
                %(commit_hash)s, %(docker_image_tag)s, %(originated_from_tournament_id)s,
                %(originated_from_hotkey)s, %(status)s, %(created_at)s, %(activated_at)s,
                %(deprecated_at)s)
        """
        
        self.client.command(query, parameters={
            'baseline_id': str(baseline.baseline_id),
            'image_type': baseline.image_type.value,
            'version': baseline.version,
            'github_repository': baseline.github_repository,
            'commit_hash': baseline.commit_hash,
            'docker_image_tag': baseline.docker_image_tag,
            'originated_from_tournament_id': str(baseline.originated_from_tournament_id) if baseline.originated_from_tournament_id else None,
            'originated_from_hotkey': baseline.originated_from_hotkey,
            'status': baseline.status.value,
            'created_at': baseline.created_at,
            'activated_at': baseline.activated_at,
            'deprecated_at': baseline.deprecated_at
        })

    @log_errors
    def update_baseline_status(
        self,
        baseline_id: UUID,
        status: BaselineStatus,
        activated_at: datetime = None,
        deprecated_at: datetime = None
    ) -> None:
        """Update the status of a baseline with appropriate timestamp."""
        baseline = self.get_baseline_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"Baseline not found: {baseline_id}")
        
        # Use provided timestamps or preserve existing
        new_activated_at = activated_at if activated_at else baseline.activated_at
        new_deprecated_at = deprecated_at if deprecated_at else baseline.deprecated_at
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (baseline_id, image_type, version, github_repository, commit_hash,
         docker_image_tag, originated_from_tournament_id, originated_from_hotkey,
         status, created_at, activated_at, deprecated_at)
        VALUES (%(baseline_id)s, %(image_type)s, %(version)s, %(github_repository)s,
                %(commit_hash)s, %(docker_image_tag)s, %(originated_from_tournament_id)s,
                %(originated_from_hotkey)s, %(status)s, %(created_at)s, %(activated_at)s,
                %(deprecated_at)s)
        """
        
        self.client.command(query, parameters={
            'baseline_id': str(baseline_id),
            'image_type': baseline.image_type.value,
            'version': baseline.version,
            'github_repository': baseline.github_repository,
            'commit_hash': baseline.commit_hash,
            'docker_image_tag': baseline.docker_image_tag,
            'originated_from_tournament_id': str(baseline.originated_from_tournament_id) if baseline.originated_from_tournament_id else None,
            'originated_from_hotkey': baseline.originated_from_hotkey,
            'status': status.value,
            'created_at': baseline.created_at,
            'activated_at': new_activated_at,
            'deprecated_at': new_deprecated_at
        })

    @log_errors
    def deprecate_baseline(self, baseline_id: UUID) -> None:
        """Set baseline status to deprecated with timestamp."""
        self.update_baseline_status(
            baseline_id=baseline_id,
            status=BaselineStatus.DEPRECATED,
            deprecated_at=datetime.now()
        )

    def _row_to_baseline(self, row, column_names) -> Baseline:
        """Convert a database row to a Baseline model."""
        data = row_to_dict(row, column_names)
        return Baseline(
            baseline_id=UUID(data['baseline_id']) if isinstance(data['baseline_id'], str) else data['baseline_id'],
            image_type=ImageType(data['image_type']),
            version=data['version'],
            github_repository=data['github_repository'],
            commit_hash=data['commit_hash'],
            docker_image_tag=data['docker_image_tag'],
            originated_from_tournament_id=UUID(data['originated_from_tournament_id']) if data['originated_from_tournament_id'] else None,
            originated_from_hotkey=data['originated_from_hotkey'],
            status=BaselineStatus(data['status']),
            created_at=data['created_at'],
            activated_at=data['activated_at'],
            deprecated_at=data['deprecated_at']
        )