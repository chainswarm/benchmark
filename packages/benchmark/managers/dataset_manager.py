import os
from pathlib import Path
from typing import List

import pandas as pd
from clickhouse_connect import get_client
from clickhouse_connect.driver import Client
from loguru import logger

from packages.benchmark.models.miner import ImageType


class DatasetManager:
    ALLOWED_FILES = [
        'transfers.parquet',
        'address_labels.parquet',
        'assets.parquet',
        'asset_prices.parquet',
    ]
    
    EXCLUDED_FILES = [
        'ground_truth.parquet',
        'META.json',
    ]

    def __init__(self, data_base_path: str = None):
        self.data_base_path = Path(data_base_path or os.environ['BENCHMARK_DATA_PATH'])
        self.data_base_path.mkdir(parents=True, exist_ok=True)
        
        self.validator_host = os.environ['VALIDATOR_CH_HOST']
        self.validator_port = int(os.environ['VALIDATOR_CH_PORT'])

    def get_dataset_path(self, network: str, processing_date: str, window_days: int) -> Path:
        """Get the local path for a dataset without downloading."""
        return self.data_base_path / network / processing_date / str(window_days)

    def check_dataset_availability(self, network: str, processing_date: str, window_days: int) -> dict:
        """
        Check if a dataset is available locally and/or in S3.
        
        Args:
            network: Network name (e.g., 'torus', 'bittensor')
            processing_date: Date string (YYYY-MM-DD)
            window_days: Window days (30 or 90)
            
        Returns:
            Dict with:
                - local_exists: bool
                - local_complete: bool
                - s3_exists: bool
                - has_ground_truth: bool
                - path: str (local path)
        """
        dataset_path = self.get_dataset_path(network, processing_date, window_days)
        
        local_exists = dataset_path.exists()
        local_complete = local_exists and self._is_dataset_complete(dataset_path)
        has_ground_truth = local_exists and (dataset_path / 'ground_truth.parquet').exists()
        
        s3_exists = False
        try:
            s3_exists = self._check_s3_exists(network, processing_date, window_days)
        except Exception as e:
            logger.warning("Failed to check S3 availability", extra={
                "network": network,
                "processing_date": processing_date,
                "window_days": window_days,
                "error": str(e)
            })
        
        return {
            'local_exists': local_complete,
            'local_complete': local_complete,
            's3_exists': s3_exists,
            'has_ground_truth': has_ground_truth,
            'path': str(dataset_path)
        }

    def _check_s3_exists(self, network: str, processing_date: str, window_days: int) -> bool:
        """Check if dataset exists in S3."""
        import boto3
        
        s3_bucket = os.environ['SYNTHETICS_S3_BUCKET']
        s3_prefix = f"snapshots/{network}/{processing_date}/{window_days}"
        
        s3_client = boto3.client(
            's3',
            endpoint_url=os.environ.get('SYNTHETICS_S3_ENDPOINT'),
            aws_access_key_id=os.environ['SYNTHETICS_S3_ACCESS_KEY'],
            aws_secret_access_key=os.environ['SYNTHETICS_S3_SECRET_KEY'],
            region_name=os.environ.get('SYNTHETICS_S3_REGION', 'us-east-1')
        )
        
        response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix, MaxKeys=1)
        
        return 'Contents' in response and len(response['Contents']) > 0

    def fetch_dataset(self, network: str, processing_date: str, window_days: int) -> Path:
        dataset_path = self.get_dataset_path(network, processing_date, window_days)
        
        if dataset_path.exists() and self._is_dataset_complete(dataset_path):
            logger.info("Dataset already exists", extra={
                "network": network,
                "processing_date": processing_date,
                "window_days": window_days
            })
            return dataset_path
        
        logger.info("Fetching dataset from S3", extra={
            "network": network,
            "processing_date": processing_date,
            "window_days": window_days
        })
        
        self._download_from_s3(network, processing_date, window_days, dataset_path)
        return dataset_path

    def prepare_miner_mount(self, dataset_path: Path) -> Path:
        mount_path = dataset_path / 'miner_mount'
        mount_path.mkdir(exist_ok=True)
        
        for filename in self.ALLOWED_FILES:
            source = dataset_path / filename
            target = mount_path / filename
            
            if source.exists() and not target.exists():
                target.symlink_to(source)
        
        logger.info("Prepared miner mount directory", extra={
            "mount_path": str(mount_path),
            "files": self.ALLOWED_FILES
        })
        
        return mount_path

    def create_miner_database(self, hotkey: str, image_type: ImageType) -> str:
        database_name = f"{image_type.value}_{hotkey}"
        
        client = self._get_validator_client()
        
        client.command(f"CREATE DATABASE IF NOT EXISTS {database_name}")
        
        schema_file = self._get_miner_schema_file(image_type)
        schema_sql = schema_file.read_text()
        
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                client.command(f"USE {database_name}; {statement}")
        
        logger.info("Created miner database", extra={
            "database_name": database_name,
            "image_type": image_type.value
        })
        
        return database_name

    def get_ground_truth(self, network: str, processing_date: str, window_days: int) -> pd.DataFrame:
        dataset_path = self.data_base_path / network / processing_date / str(window_days)
        ground_truth_path = dataset_path / 'ground_truth.parquet'
        
        if not ground_truth_path.exists():
            raise FileNotFoundError(f"Ground truth not found: {ground_truth_path}")
        
        return pd.read_parquet(ground_truth_path)

    def get_data_pipeline_client(self, network: str) -> Client:
        network_upper = network.upper()
        
        host = os.environ[f'{network_upper}_DATA_PIPELINE_CH_HOST']
        port = int(os.environ[f'{network_upper}_DATA_PIPELINE_CH_PORT'])
        database = os.environ[f'{network_upper}_DATA_PIPELINE_CH_DATABASE']
        
        return get_client(host=host, port=port, database=database)

    def list_available_datasets(self) -> List[dict]:
        datasets = []
        
        for network_dir in self.data_base_path.iterdir():
            if not network_dir.is_dir():
                continue
            
            for date_dir in network_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                
                for window_dir in date_dir.iterdir():
                    if not window_dir.is_dir():
                        continue
                    
                    if self._is_dataset_complete(window_dir):
                        datasets.append({
                            'network': network_dir.name,
                            'processing_date': date_dir.name,
                            'window_days': int(window_dir.name)
                        })
        
        return datasets

    def _get_validator_client(self) -> Client:
        return get_client(
            host=self.validator_host,
            port=self.validator_port,
            database='default'
        )

    def _is_dataset_complete(self, dataset_path: Path) -> bool:
        for filename in self.ALLOWED_FILES:
            if not (dataset_path / filename).exists():
                return False
        return True

    def _download_from_s3(self, network: str, processing_date: str, window_days: int, target_path: Path) -> None:
        import boto3
        
        s3_bucket = os.environ['SYNTHETICS_S3_BUCKET']
        s3_prefix = f"snapshots/{network}/{processing_date}/{window_days}"
        
        s3_client = boto3.client(
            's3',
            endpoint_url=os.environ.get('SYNTHETICS_S3_ENDPOINT'),
            aws_access_key_id=os.environ['SYNTHETICS_S3_ACCESS_KEY'],
            aws_secret_access_key=os.environ['SYNTHETICS_S3_SECRET_KEY'],
            region_name=os.environ.get('SYNTHETICS_S3_REGION', 'us-east-1')
        )
        
        target_path.mkdir(parents=True, exist_ok=True)
        
        response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
        
        if 'Contents' not in response:
            raise FileNotFoundError(f"No files found in S3 at {s3_prefix}")
        
        for obj in response['Contents']:
            key = obj['Key']
            filename = Path(key).name
            
            if filename in self.EXCLUDED_FILES:
                continue
            
            local_file = target_path / filename
            
            logger.debug("Downloading file from S3", extra={
                "key": key,
                "local_path": str(local_file)
            })
            
            s3_client.download_file(s3_bucket, key, str(local_file))
        
        ground_truth_key = f"{s3_prefix}/ground_truth.parquet"
        ground_truth_local = target_path / 'ground_truth.parquet'
        
        try:
            s3_client.download_file(s3_bucket, ground_truth_key, str(ground_truth_local))
        except Exception as e:
            logger.warning("Failed to download ground truth", extra={"error": str(e)})

    def _get_miner_schema_file(self, image_type: ImageType) -> Path:
        schema_dir = Path(__file__).parent.parent.parent / 'storage' / 'schema' / 'benchmark'
        
        if image_type == ImageType.ANALYTICS:
            return schema_dir / 'miner_analytics_schema.sql'
        else:
            return schema_dir / 'miner_ml_schema.sql'