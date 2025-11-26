from pathlib import Path
from typing import List, Dict
import pandas as pd
import json
import hashlib
from loguru import logger
from datetime import datetime, timedelta, timezone
import os
from celery_singleton import Singleton

PROJECT_ROOT = Path(__file__).resolve().parents[3]

from packages.jobs.base import BaseTaskContext
from packages.jobs.celery_app import celery_app
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.storage.repositories import get_connection_params, ClientFactory
from packages import setup_logger


class ExportBatchTask(BaseDataPipelineTask, Singleton):

    def execute_task(self, context: BaseTaskContext):
        service_name = f'export-{context.network}-batch-export'
        setup_logger(service_name)

        connection_params = get_connection_params(context.network)
        
        base_path = Path(os.getenv('BATCH_EXPORT_PATH', str(PROJECT_ROOT / 'data' / 'batches')))
        
        s3_enabled = os.getenv('SYNTHETICS_S3_ENABLED', 'false').lower() == 'true'
        s3_endpoint = os.getenv('SYNTHETICS_S3_ENDPOINT')
        s3_access_key = os.getenv('SYNTHETICS_S3_ACCESS_KEY')
        s3_secret_key = os.getenv('SYNTHETICS_S3_SECRET_KEY')
        s3_bucket = os.getenv('SYNTHETICS_S3_BUCKET')
        s3_region = os.getenv('SYNTHETICS_S3_REGION', 'us-east-1')

        client_factory = ClientFactory(connection_params)
        with client_factory.client_context() as client:
            logger.info(f"Exporting batch: {context.network}/{context.processing_date}/{context.window_days}d")
            
            export_dir = self._get_export_path(base_path, context.network, context.processing_date, context.window_days)
            export_dir.mkdir(parents=True, exist_ok=True)
            
            file_paths = {}
            
            # Export transfers (merged core + synthetic via VIEW)
            transfers_count = self._export_transfers(client, export_dir, file_paths)
            
            # Export address labels (merged core + synthetic via VIEW)
            address_labels_count = self._export_address_labels(client, export_dir, file_paths)
            
            # Export ground truth (for evaluation - synthetic patterns only)
            ground_truth_count = self._export_ground_truth(client, export_dir, file_paths)
            
            # Also export asset prices and assets for complete compatibility
            self._export_asset_prices(client, export_dir, context.processing_date, context.window_days, file_paths)
            self._export_assets(client, export_dir, file_paths)

            meta = self._generate_metadata(
                context.network, context.processing_date, context.window_days,
                file_paths,
                transfers_count=transfers_count,
                address_labels_count=address_labels_count,
                ground_truth_count=ground_truth_count
            )
            
            meta_path = export_dir / 'META.json'
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
            
            logger.info(f"Batch exported to {export_dir}")

            
            s3_uploaded = False
            if s3_enabled:
                if not all([s3_endpoint, s3_access_key, s3_secret_key, s3_bucket]):
                    logger.error("S3 upload enabled but missing required S3 credentials")
                    raise ValueError("Missing required S3 configuration")
                
                try:
                    self._upload_to_s3(
                        s3_endpoint, s3_access_key, s3_secret_key, s3_bucket, s3_region,
                        export_dir, context.network, context.processing_date, context.window_days
                    )
                    s3_uploaded = True

                except Exception as e:
                    logger.error(f"S3 upload failed: {e}")
                    raise
            
            return {
                'export_path': str(export_dir),
                'meta': meta,
                's3_uploaded': s3_uploaded,
            }
    
    def _get_export_path(
        self,
        base_path: Path,
        network: str,
        processing_date: str,
        window_days: int
    ) -> Path:
        # Path structure: snapshots/{network}/{processing_date}/{window_days}
        # This matches S3Extractor's expected path structure
        return base_path / 'snapshots' / network / processing_date / str(window_days)

    def _export_transfers(self, client, export_dir: Path, file_paths: dict) -> int:
        """Export transfers from core_transfers VIEW (merged core + synthetic).
        
        This exports the unified view that combines:
        - core_transfers_referential (real data from data-pipeline)
        - synthetics_transfers (generated synthetic data)
        
        The exported file is compatible with analytics-pipeline expectations.
        """
        query = """
            SELECT
                processing_date,
                window_days,
                tx_id,
                event_index,
                edge_index,
                block_height,
                block_timestamp,
                from_address,
                to_address,
                asset_symbol,
                asset_contract,
                amount,
                amount_usd,
                fee
            FROM core_transfers
        """
        
        try:
            df = client.query_df(query)
            
            if not df.empty:
                path = export_dir / 'transfers.parquet'
                df.to_parquet(path, index=False, compression='snappy')
                file_paths['transfers'] = str(path)
                logger.info(f"Exported transfers.parquet: {len(df)} rows")
                return len(df)
            return 0
        except Exception as e:
            logger.warning(f"Could not export transfers: {e}")
            return 0

    def _export_parquet(self, data: List[Dict], path: Path) -> str:
        df = pd.DataFrame(data)
        df.to_parquet(path, index=False, compression='snappy')
        logger.info(f"Exported {path.name}: {len(df)} rows")
        return str(path)
    
    def _export_asset_prices(self, client, export_dir: Path, processing_date: str, window_days: int, file_paths: dict):
        """Export asset prices for the window period."""
        from datetime import datetime as dt_module
        
        end_date = dt_module.strptime(processing_date, '%Y-%m-%d').date()
        start_date = end_date - timedelta(days=window_days)
        
        query = """
            SELECT *
            FROM core_asset_prices
            WHERE price_date >= %(start_date)s
              AND price_date <= %(end_date)s
        """
        
        try:
            df = client.query_df(query, parameters={
                'start_date': start_date,
                'end_date': end_date
            })
            
            if not df.empty:
                path = export_dir / 'asset_prices.parquet'
                df.to_parquet(path, index=False, compression='snappy')
                file_paths['asset_prices'] = str(path)
                logger.info(f"Exported asset_prices.parquet: {len(df)} rows")
        except Exception as e:
            logger.warning(f"Could not export asset prices: {e}")
    
    def _export_assets(self, client, export_dir: Path, file_paths: dict):
        """Export asset metadata."""
        query = "SELECT * FROM core_assets"
        
        try:
            df = client.query_df(query)
            
            if not df.empty:
                path = export_dir / 'assets.parquet'
                df.to_parquet(path, index=False, compression='snappy')
                file_paths['assets'] = str(path)
                logger.info(f"Exported assets.parquet: {len(df)} rows")
        except Exception as e:
            logger.warning(f"Could not export assets: {e}")

    def _export_address_labels(self, client, export_dir: Path, file_paths: dict) -> int:
        """Export address labels from core_address_labels VIEW (merged core + synthetic).
        
        This exports the unified view that combines:
        - core_address_labels_referential (real labels from data-pipeline)
        - synthetics_address_labels (generated synthetic flagged addresses)
        
        The exported file is compatible with analytics-pipeline expectations.
        """
        query = """
            SELECT
                processing_date,
                window_days,
                network,
                network_type,
                address,
                label,
                address_type,
                address_subtype,
                trust_level,
                source,
                risk_level,
                confidence_score,
                created_timestamp,
                updated_timestamp
            FROM core_address_labels
        """
        
        try:
            df = client.query_df(query)
            
            if not df.empty:
                path = export_dir / 'address_labels.parquet'
                df.to_parquet(path, index=False, compression='snappy')
                file_paths['address_labels'] = str(path)
                logger.info(f"Exported address_labels.parquet: {len(df)} rows")
                return len(df)
            return 0
        except Exception as e:
            logger.warning(f"Could not export address labels: {e}")
            return 0
    
    def _export_ground_truth(self, client, export_dir: Path, file_paths: dict) -> int:
        """Export ground truth labels for synthetic addresses.
        
        This exports synthetics_ground_truth which contains the role and pattern
        information for addresses that are part of synthetic patterns.
        
        Used for:
        - Evaluation of miner risk scoring accuracy
        - Pattern replay and testing
        - ML training/validation ground truth
        """
        query = """
            SELECT
                processing_date,
                window_days,
                address,
                role,
                pattern_type,
                pattern_instance_id,
                hop_distance,
                flagged_address,
                flag_type
            FROM synthetics_ground_truth
        """
        
        try:
            df = client.query_df(query)
            
            if not df.empty:
                path = export_dir / 'ground_truth.parquet'
                df.to_parquet(path, index=False, compression='snappy')
                file_paths['ground_truth'] = str(path)
                logger.info(f"Exported ground_truth.parquet: {len(df)} rows")
                return len(df)
            return 0
        except Exception as e:
            logger.warning(f"Could not export ground truth: {e}")
            return 0

    def _generate_metadata(
            self,
            network: str,
            processing_date: str,
            window_days: int,
            file_paths: dict,
            transfers_count: int = 0,
            address_labels_count: int = 0,
            ground_truth_count: int = 0
    ) -> dict:
        logger.info("Generating metadata")

        hashes = {}
        for name, path in file_paths.items():
            hashes[f"{name}.parquet"] = self._compute_file_hash(path)

        meta = {
            'schema_version': '1.0.0',
            'batch_id': f"{network}-{processing_date}-{window_days}d",
            'network': network,
            'processing_date': processing_date,
            'window_days': window_days,
            'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),

            'counts': {
                'transfers': transfers_count,
                'address_labels': address_labels_count,
                'ground_truth': ground_truth_count,
            },

            'sha256': hashes
        }

        return meta
    
    def _compute_file_hash(self, file_path: str) -> str:
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _upload_to_s3(
        self,
        s3_endpoint: str,
        s3_access_key: str,
        s3_secret_key: str,
        s3_bucket: str,
        s3_region: str,
        local_dir: Path,
        network: str,
        processing_date: str,
        window_days: int
    ):
        import boto3
        from botocore.exceptions import ClientError
        
        logger.info(f"Uploading risk scoring batch to S3: {s3_bucket}")
        
        s3 = boto3.client(
            's3',
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
            region_name=s3_region
        )
        
        s3_prefix = f"snapshots/{network}/{processing_date}/{window_days}"
        
        uploaded_count = 0
        for file_path in local_dir.glob('*'):
            if file_path.is_file():
                s3_key = f"{s3_prefix}/{file_path.name}"
                
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                logger.info(f"Uploading {file_path.name} to s3://{s3_bucket}/{s3_key} ({file_size_mb:.2f} MB)")
                
                try:
                    s3.upload_file(
                        str(file_path),
                        s3_bucket,
                        s3_key,
                        ExtraArgs={'ACL': 'public-read'}
                    )
                    logger.info(f"Uploaded {file_path.name} ({file_size_mb:.2f} MB)")
                    uploaded_count += 1
                except ClientError as e:
                    logger.error(f"Failed to upload {file_path.name}: {e}")
                    raise
        
        logger.success(f"Upload completed: {uploaded_count} files uploaded to s3://{s3_bucket}/{s3_prefix}")


@celery_app.task(
    bind=True,
    base=ExportBatchTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 24,
        'countdown': 600
    },
    time_limit=7200,
    soft_time_limit=7080
)
def export_batch_task(
    self,
    network: str,
    window_days: int,
    processing_date: str
):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date
    )
    
    return self.run(context)

