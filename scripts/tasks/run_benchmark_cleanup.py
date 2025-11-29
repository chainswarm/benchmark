import argparse
import sys
from uuid import UUID

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.benchmark_cleanup_task import BenchmarkCleanupTask


def main():
    parser = argparse.ArgumentParser(
        description='Clean up resources after a benchmark epoch completes'
    )
    parser.add_argument(
        '--epoch-id',
        required=True,
        help='UUID of the benchmark epoch to clean up'
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
        '--skip-docker-cleanup',
        action='store_true',
        help='Skip Docker image removal'
    )
    parser.add_argument(
        '--skip-repo-cleanup',
        action='store_true',
        help='Skip repository cleanup'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    try:
        epoch_uuid = UUID(args.epoch_id)
    except ValueError:
        logger.error("Invalid epoch-id format. Must be a valid UUID.")
        sys.exit(1)
    
    logger.info("Starting benchmark cleanup", extra={
        "epoch_id": str(epoch_uuid),
        "hotkey": args.hotkey,
        "image_type": args.image_type,
        "skip_docker_cleanup": args.skip_docker_cleanup,
        "skip_repo_cleanup": args.skip_repo_cleanup
    })
    
    context = {
        'epoch_id': str(epoch_uuid),
        'hotkey': args.hotkey,
        'image_type': args.image_type
    }
    
    task = BenchmarkCleanupTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Cleanup completed successfully", extra=result)
        else:
            logger.error("Cleanup failed", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Cleanup error", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()