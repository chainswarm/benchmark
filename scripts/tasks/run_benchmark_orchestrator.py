import argparse
import sys
from datetime import date, datetime

from dotenv import load_dotenv
from loguru import logger

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.jobs.tasks.benchmark_orchestrator_task import BenchmarkOrchestratorTask
from packages.jobs.tasks.dataset_preparation_task import (
    DatasetPreparationTask,
    get_standard_benchmark_datasets,
)


def validate_datasets_before_benchmark(processing_date: str) -> bool:
    """
    Pre-validate all required datasets before starting the benchmark.
    
    Args:
        processing_date: The processing date in YYYY-MM-DD format
        
    Returns:
        True if all datasets are available
        
    Raises:
        ValueError: If any dataset is missing from S3
    """
    logger.info("Pre-validating datasets for benchmark", extra={
        "processing_date": processing_date
    })
    
    datasets = get_standard_benchmark_datasets(processing_date)
    
    context = {
        'datasets': datasets,
        'fail_on_missing': True
    }
    
    task = DatasetPreparationTask()
    result = task.execute_task(context)
    
    logger.info("All datasets validated and available", extra={
        "prepared_count": len(result['prepared_datasets'])
    })
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Run the complete benchmark orchestration pipeline. '
                    'Pre-validates datasets and fails if any are missing from S3.'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images to benchmark'
    )
    parser.add_argument(
        '--test-date',
        required=False,
        help='Test date (YYYY-MM-DD format). Defaults to today.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate datasets and show what would be executed, without running'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    test_date = args.test_date or date.today().isoformat()
    
    try:
        datetime.strptime(test_date, '%Y-%m-%d')
    except ValueError:
        logger.error("Invalid date format. Please use YYYY-MM-DD format.")
        sys.exit(1)
    
    logger.info("Starting benchmark orchestration", extra={
        "image_type": args.image_type,
        "test_date": test_date,
        "dry_run": args.dry_run
    })
    
    try:
        validate_datasets_before_benchmark(processing_date=test_date)
        logger.info("Dataset validation passed")
    except ValueError as e:
        logger.error("Dataset validation failed - cannot proceed with benchmark", extra={
            "error": str(e)
        })
        sys.exit(1)
    
    if args.dry_run:
        logger.info("DRY RUN - Would execute benchmark with the following configuration:", extra={
            "image_type": args.image_type,
            "test_date": test_date,
            "networks": ['torus', 'bittensor'],
            "window_days_options": [30, 90],
            "test_matrix": [
                {'network': 'torus', 'window_days': 30},
                {'network': 'torus', 'window_days': 90},
                {'network': 'bittensor', 'window_days': 30},
                {'network': 'bittensor', 'window_days': 90},
            ]
        })
        logger.info("DRY RUN complete - no benchmark executed")
        return
    
    context = {
        'image_type': args.image_type,
        'test_date': test_date
    }
    
    task = BenchmarkOrchestratorTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Benchmark orchestration completed successfully", extra=result)
        else:
            logger.warning("Benchmark orchestration completed with issues", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Benchmark orchestration failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()