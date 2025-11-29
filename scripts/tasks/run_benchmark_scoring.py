import argparse
import sys
from uuid import UUID

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.benchmark_scoring_task import BenchmarkScoringTask


def main():
    parser = argparse.ArgumentParser(
        description='Calculate final scores for a benchmark epoch'
    )
    parser.add_argument(
        '--epoch-id',
        required=True,
        help='UUID of the benchmark epoch to score'
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
    args = parser.parse_args()
    
    load_dotenv()
    
    try:
        epoch_uuid = UUID(args.epoch_id)
    except ValueError:
        logger.error("Invalid epoch-id format. Must be a valid UUID.")
        sys.exit(1)
    
    logger.info("Starting benchmark scoring", extra={
        "epoch_id": str(epoch_uuid),
        "hotkey": args.hotkey,
        "image_type": args.image_type
    })
    
    context = {
        'epoch_id': str(epoch_uuid),
        'hotkey': args.hotkey,
        'image_type': args.image_type
    }
    
    task = BenchmarkScoringTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Scoring completed successfully", extra={
                "epoch_id": str(epoch_uuid),
                "final_score": result.get('final_score')
            })
        elif result.get('status') == 'no_runs':
            logger.warning("No runs found for epoch - cannot calculate score", extra={
                "epoch_id": str(epoch_uuid)
            })
            sys.exit(1)
        else:
            logger.error("Scoring failed", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Scoring error", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()