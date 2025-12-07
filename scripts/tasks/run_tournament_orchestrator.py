import argparse
import sys
from datetime import date

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.tournament_orchestrator_task import TournamentOrchestratorTask
from packages.jobs.base import TournamentTaskContext


def main():
    parser = argparse.ArgumentParser(
        description='Run the tournament orchestrator to manage lifecycle transitions.'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images'
    )
    parser.add_argument(
        '--tournament-id',
        required=False,
        help='Specific tournament UUID to process (optional, processes all if not provided)'
    )
    parser.add_argument(
        '--test-date',
        required=False,
        help='Test date (YYYY-MM-DD format). Defaults to today.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    test_date = args.test_date or date.today().isoformat()
    
    logger.info("Starting tournament orchestrator", extra={
        "image_type": args.image_type,
        "tournament_id": args.tournament_id,
        "test_date": test_date,
        "dry_run": args.dry_run
    })
    
    if args.dry_run:
        logger.info("DRY RUN - Would execute tournament orchestrator with:", extra={
            "image_type": args.image_type,
            "tournament_id": args.tournament_id,
            "test_date": test_date
        })
        return
    
    context = TournamentTaskContext(
        tournament_id=args.tournament_id,
        image_type=args.image_type,
        test_date=test_date
    )
    
    task = TournamentOrchestratorTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Tournament orchestration completed", extra=result)
        else:
            logger.warning("Tournament orchestration issue", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Tournament orchestration failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
