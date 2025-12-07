import argparse
import sys
from datetime import date

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.tournament_day_execution_task import TournamentDayExecutionTask
from packages.jobs.base import TournamentTaskContext


def main():
    parser = argparse.ArgumentParser(
        description='Execute daily benchmarks for all tournament participants.'
    )
    parser.add_argument(
        '--tournament-id',
        required=True,
        help='Tournament UUID to execute'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images'
    )
    parser.add_argument(
        '--test-date',
        required=True,
        help='Test date (YYYY-MM-DD format)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    logger.info("Starting tournament day execution", extra={
        "tournament_id": args.tournament_id,
        "image_type": args.image_type,
        "test_date": args.test_date,
        "dry_run": args.dry_run
    })
    
    if args.dry_run:
        logger.info("DRY RUN - Would execute tournament day with:", extra={
            "tournament_id": args.tournament_id,
            "image_type": args.image_type,
            "test_date": args.test_date
        })
        return
    
    context = TournamentTaskContext(
        tournament_id=args.tournament_id,
        image_type=args.image_type,
        test_date=args.test_date
    )
    
    task = TournamentDayExecutionTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Tournament day execution completed", extra=result)
        else:
            logger.warning("Tournament day execution issue", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Tournament day execution failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()