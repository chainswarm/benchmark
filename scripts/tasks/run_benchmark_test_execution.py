import argparse
import sys
from datetime import date, datetime
from uuid import UUID

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.benchmark_test_execution_task import BenchmarkTestExecutionTask


def main():
    parser = argparse.ArgumentParser(
        description='Run a single benchmark test execution for a miner'
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
        '--test-date',
        required=False,
        help='Test date (YYYY-MM-DD format). Defaults to today.'
    )
    parser.add_argument(
        '--network',
        required=True,
        choices=['torus', 'bittensor'],
        help='Network for the test'
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
        required=False,
        help='Processing date (YYYY-MM-DD format). Defaults to test-date.'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    try:
        epoch_uuid = UUID(args.epoch_id)
    except ValueError:
        logger.error("Invalid epoch-id format. Must be a valid UUID.")
        sys.exit(1)
    
    test_date = args.test_date or date.today().isoformat()
    processing_date = args.processing_date or test_date
    
    try:
        datetime.strptime(test_date, '%Y-%m-%d')
        datetime.strptime(processing_date, '%Y-%m-%d')
    except ValueError:
        logger.error("Invalid date format. Please use YYYY-MM-DD format.")
        sys.exit(1)
    
    logger.info("Starting benchmark test execution", extra={
        "epoch_id": str(epoch_uuid),
        "hotkey": args.hotkey,
        "image_type": args.image_type,
        "test_date": test_date,
        "network": args.network,
        "window_days": args.window_days,
        "processing_date": processing_date
    })
    
    context = {
        'epoch_id': str(epoch_uuid),
        'hotkey': args.hotkey,
        'image_type': args.image_type,
        'test_date': test_date,
        'network': args.network,
        'window_days': args.window_days,
        'processing_date': processing_date
    }
    
    task = BenchmarkTestExecutionTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Test execution completed successfully", extra=result)
        elif result.get('status') == 'timeout':
            logger.warning("Test execution timed out", extra=result)
            sys.exit(1)
        else:
            logger.error("Test execution failed", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Test execution error", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()