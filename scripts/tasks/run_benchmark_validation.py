import argparse
import sys
from uuid import UUID

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.benchmark_validation_task import BenchmarkValidationTask


def main():
    parser = argparse.ArgumentParser(
        description='Run validation for a benchmark test execution run'
    )
    parser.add_argument(
        '--run-id',
        required=True,
        help='UUID of the test run to validate'
    )
    parser.add_argument(
        '--epoch-id',
        required=True,
        help='UUID of the benchmark epoch'
    )
    parser.add_argument(
        '--hotkey',
        required=True,
        help='Miner hotkey'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner image'
    )
    parser.add_argument(
        '--network',
        required=True,
        choices=['torus', 'bittensor'],
        help='Network for validation'
    )
    parser.add_argument(
        '--window-days',
        required=True,
        type=int,
        choices=[30, 90],
        help='Window days for the dataset'
    )
    parser.add_argument(
        '--processing-date',
        required=True,
        help='Processing date (YYYY-MM-DD format)'
    )
    parser.add_argument(
        '--miner-database',
        required=True,
        help='Name of the miner database to validate results from'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    try:
        run_uuid = UUID(args.run_id)
        epoch_uuid = UUID(args.epoch_id)
    except ValueError as e:
        logger.error("Invalid UUID format", extra={"error": str(e)})
        sys.exit(1)
    
    logger.info("Starting benchmark validation", extra={
        "run_id": str(run_uuid),
        "epoch_id": str(epoch_uuid),
        "hotkey": args.hotkey,
        "image_type": args.image_type,
        "network": args.network,
        "window_days": args.window_days,
        "processing_date": args.processing_date,
        "miner_database": args.miner_database
    })
    
    context = {
        'run_id': str(run_uuid),
        'epoch_id': str(epoch_uuid),
        'hotkey': args.hotkey,
        'image_type': args.image_type,
        'network': args.network,
        'window_days': args.window_days,
        'processing_date': args.processing_date,
        'miner_database': args.miner_database
    }
    
    task = BenchmarkValidationTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            if result.get('data_correctness_passed'):
                logger.info("Validation completed - data correctness PASSED", extra=result)
            else:
                logger.warning("Validation completed - data correctness FAILED", extra=result)
                sys.exit(1)
        else:
            logger.error("Validation failed", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Validation error", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()