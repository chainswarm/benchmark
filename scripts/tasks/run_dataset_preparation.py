import argparse
import sys
from datetime import date, datetime

from dotenv import load_dotenv
from loguru import logger

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.jobs.tasks.dataset_preparation_task import (
    DatasetPreparationTask,
    get_standard_benchmark_datasets,
)


def main():
    parser = argparse.ArgumentParser(
        description='Prepare and validate datasets for benchmark execution. '
                    'Downloads from S3 if not locally available. Fails if S3 does not have the data.'
    )
    parser.add_argument(
        '--processing-date',
        required=False,
        help='Processing date (YYYY-MM-DD format). Defaults to today.'
    )
    parser.add_argument(
        '--network',
        required=False,
        choices=['torus', 'bittensor', 'all'],
        default='all',
        help='Network to prepare datasets for (default: all)'
    )
    parser.add_argument(
        '--window-days',
        required=False,
        type=int,
        choices=[30, 90],
        default=None,
        help='Window days for dataset (default: both 30 and 90)'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    processing_date = args.processing_date or date.today().isoformat()
    
    try:
        datetime.strptime(processing_date, '%Y-%m-%d')
    except ValueError:
        logger.error("Invalid date format. Please use YYYY-MM-DD format.")
        sys.exit(1)
    
    if args.network == 'all' and args.window_days is None:
        datasets = get_standard_benchmark_datasets(processing_date)
    else:
        datasets = []
        networks = ['torus', 'bittensor'] if args.network == 'all' else [args.network]
        window_days_list = [30, 90] if args.window_days is None else [args.window_days]
        
        for network in networks:
            for window_days in window_days_list:
                datasets.append({
                    'network': network,
                    'processing_date': processing_date,
                    'window_days': window_days
                })
    
    logger.info("Preparing datasets", extra={
        "processing_date": processing_date,
        "dataset_count": len(datasets),
        "datasets": datasets
    })
    
    context = {
        'datasets': datasets,
        'fail_on_missing': True
    }
    
    task = DatasetPreparationTask()
    
    try:
        result = task.execute_task(context)
        
        logger.info("All datasets prepared successfully", extra={
            "prepared_count": len(result['prepared_datasets']),
            "prepared_datasets": result['prepared_datasets']
        })
                
    except ValueError as e:
        logger.error("Dataset preparation failed - missing datasets in S3", extra={"error": str(e)})
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error during dataset preparation", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()