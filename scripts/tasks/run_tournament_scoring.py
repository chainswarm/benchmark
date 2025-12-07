import argparse
import sys

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.tournament_scoring_task import TournamentScoringTask
from packages.jobs.base import TournamentTaskContext


def main():
    parser = argparse.ArgumentParser(
        description='Calculate final scores and rankings for a tournament.'
    )
    parser.add_argument(
        '--tournament-id',
        required=True,
        help='Tournament UUID to score'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    logger.info("Starting tournament scoring", extra={
        "tournament_id": args.tournament_id,
        "image_type": args.image_type,
        "dry_run": args.dry_run
    })
    
    if args.dry_run:
        logger.info("DRY RUN - Would calculate scores with:", extra={
            "tournament_id": args.tournament_id,
            "image_type": args.image_type,
            "scoring_weights": {
                "pattern_accuracy": 0.50,
                "data_correctness": 0.30,
                "performance": 0.20
            }
        })
        return
    
    context = TournamentTaskContext(
        tournament_id=args.tournament_id,
        image_type=args.image_type,
        test_date=None
    )
    
    task = TournamentScoringTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Tournament scoring completed", extra=result)
        elif result.get('status') == 'no_winner':
            logger.warning("Tournament scoring completed - no winner", extra=result)
        else:
            logger.warning("Tournament scoring issue", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Tournament scoring failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()