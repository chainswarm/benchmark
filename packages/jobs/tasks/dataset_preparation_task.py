from dataclasses import dataclass
from typing import List, Optional

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.jobs.celery_app import celery_app


@dataclass
class DatasetConfig:
    network: str
    processing_date: str
    window_days: int


class DatasetPreparationTask(BaseTask, Singleton):

    def execute_task(self, context: dict) -> dict:
        datasets_config = context.get('datasets', [])
        fail_on_missing = context.get('fail_on_missing', True)
        
        logger.info("Starting dataset preparation", extra={
            "dataset_count": len(datasets_config),
            "fail_on_missing": fail_on_missing
        })
        
        dataset_manager = DatasetManager()
        
        prepared_datasets = []
        missing_datasets = []
        errors = []
        
        for ds_config in datasets_config:
            network = ds_config['network']
            processing_date = ds_config['processing_date']
            window_days = ds_config['window_days']
            
            logger.info("Preparing dataset", extra={
                "network": network,
                "processing_date": processing_date,
                "window_days": window_days
            })
            
            try:
                dataset_available = dataset_manager.check_dataset_availability(
                    network=network,
                    processing_date=processing_date,
                    window_days=window_days
                )
                
                if not dataset_available['local_exists']:
                    if not dataset_available['s3_exists']:
                        error_msg = f"Dataset not available in S3: {network}/{processing_date}/{window_days}"
                        logger.error(error_msg)
                        missing_datasets.append({
                            'network': network,
                            'processing_date': processing_date,
                            'window_days': window_days,
                            'reason': 'not_in_s3'
                        })
                        errors.append(error_msg)
                        continue
                    
                    dataset_path = dataset_manager.fetch_dataset(
                        network=network,
                        processing_date=processing_date,
                        window_days=window_days
                    )
                    
                    logger.info("Dataset downloaded successfully", extra={
                        "network": network,
                        "processing_date": processing_date,
                        "window_days": window_days,
                        "path": str(dataset_path)
                    })
                else:
                    dataset_path = dataset_manager.get_dataset_path(
                        network=network,
                        processing_date=processing_date,
                        window_days=window_days
                    )
                    logger.info("Dataset already available locally", extra={
                        "network": network,
                        "processing_date": processing_date,
                        "window_days": window_days,
                        "path": str(dataset_path)
                    })
                
                prepared_datasets.append({
                    'network': network,
                    'processing_date': processing_date,
                    'window_days': window_days,
                    'path': str(dataset_path),
                    'has_ground_truth': dataset_available.get('has_ground_truth', False)
                })
                
            except FileNotFoundError as e:
                error_msg = f"Dataset not found: {network}/{processing_date}/{window_days} - {str(e)}"
                logger.error(error_msg)
                missing_datasets.append({
                    'network': network,
                    'processing_date': processing_date,
                    'window_days': window_days,
                    'reason': 'download_failed',
                    'error': str(e)
                })
                errors.append(error_msg)
                
            except Exception as e:
                error_msg = f"Error preparing dataset {network}/{processing_date}/{window_days}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                missing_datasets.append({
                    'network': network,
                    'processing_date': processing_date,
                    'window_days': window_days,
                    'reason': 'error',
                    'error': str(e)
                })
                errors.append(error_msg)
        
        all_prepared = len(missing_datasets) == 0
        
        if not all_prepared and fail_on_missing:
            logger.error("Dataset preparation failed - missing datasets", extra={
                "prepared_count": len(prepared_datasets),
                "missing_count": len(missing_datasets),
                "missing_datasets": missing_datasets
            })
            raise ValueError(
                f"Failed to prepare {len(missing_datasets)} dataset(s): {', '.join(errors)}"
            )
        
        logger.info("Dataset preparation completed", extra={
            "prepared_count": len(prepared_datasets),
            "missing_count": len(missing_datasets),
            "status": "success" if all_prepared else "partial"
        })
        
        return {
            "status": "success" if all_prepared else "partial",
            "prepared_datasets": prepared_datasets,
            "missing_datasets": missing_datasets,
            "errors": errors
        }


@celery_app.task(
    bind=True,
    base=DatasetPreparationTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 60
    },
    time_limit=1800,
    soft_time_limit=1700
)
def dataset_preparation_task(
    self,
    datasets: List[dict],
    fail_on_missing: bool = True,
):
    context = {
        'datasets': datasets,
        'fail_on_missing': fail_on_missing
    }
    
    return self.run(context)


def get_standard_benchmark_datasets(processing_date: str) -> List[dict]:
    return [
        {'network': 'torus', 'processing_date': processing_date, 'window_days': 30},
        {'network': 'torus', 'processing_date': processing_date, 'window_days': 90},
        {'network': 'bittensor', 'processing_date': processing_date, 'window_days': 30},
        {'network': 'bittensor', 'processing_date': processing_date, 'window_days': 90},
    ]