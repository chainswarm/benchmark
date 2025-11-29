import argparse
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.jobs.tasks.container_run_task import ContainerRunTask


def main():
    parser = argparse.ArgumentParser(
        description='Run a miner container with proper dataset mounting'
    )
    parser.add_argument('--hotkey', required=True, help='Miner hotkey')
    parser.add_argument('--image-type', required=True, choices=['analytics', 'ml'], help='Image type')
    parser.add_argument(
        '--network',
        required=True,
        choices=['torus', 'bittensor'],
        help='Network for dataset selection'
    )
    parser.add_argument(
        '--processing-date',
        required=True,
        help='Processing date (YYYY-MM-DD format)'
    )
    parser.add_argument(
        '--window-days',
        required=True,
        type=int,
        choices=[30, 90],
        help='Window days for dataset selection'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='Timeout in seconds (default: from BENCHMARK_MAX_EXECUTION_TIME env)'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    timeout = args.timeout or int(os.getenv('BENCHMARK_MAX_EXECUTION_TIME', '3600'))
    
    dataset_manager = DatasetManager()
    
    try:
        dataset_path = dataset_manager.fetch_dataset(
            network=args.network,
            processing_date=args.processing_date,
            window_days=args.window_days
        )
    except FileNotFoundError as e:
        logger.error("Dataset not available in S3 - benchmark cannot proceed", extra={
            "network": args.network,
            "processing_date": args.processing_date,
            "window_days": args.window_days,
            "error": str(e)
        })
        sys.exit(1)
    
    mount_path = dataset_manager.prepare_miner_mount(dataset_path)
    
    image_tag = f"{args.image_type}_{args.hotkey}:latest"
    miner_database = f"{args.image_type}_{args.hotkey}"
    
    logger.info("Prepared container run context", extra={
        "hotkey": args.hotkey,
        "image_type": args.image_type,
        "network": args.network,
        "processing_date": args.processing_date,
        "window_days": args.window_days,
        "dataset_path": str(dataset_path),
        "mount_path": str(mount_path),
        "image_tag": image_tag,
        "miner_database": miner_database,
        "timeout": timeout
    })
    
    context = {
        'image_tag': image_tag,
        'data_mount_path': str(mount_path),
        'miner_database': miner_database,
        'hotkey': args.hotkey,
        'image_type': args.image_type,
        'timeout': timeout
    }
    
    task = ContainerRunTask()
    result = task.execute_task(context)
    
    if not result.get('success', False):
        logger.error("Container run failed", extra=result)
        sys.exit(1)
    
    logger.info("Container run completed successfully", extra=result)


if __name__ == "__main__":
    main()