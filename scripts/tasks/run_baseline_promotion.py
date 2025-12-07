import argparse
import sys

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.baseline_promotion_task import BaselinePromotionTask
from packages.jobs.base import TournamentTaskContext


def main():
    parser = argparse.ArgumentParser(
        description='Promote tournament winner as the new baseline.'
    )
    parser.add_argument(
        '--tournament-id',
        required=True,
        help='Tournament UUID whose winner to promote'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images'
    )
    parser.add_argument(
        '--winner-hotkey',
        required=True,
        help='Winner hotkey to promote as baseline'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    logger.info("Starting baseline promotion", extra={
        "tournament_id": args.tournament_id,
        "image_type": args.image_type,
        "winner_hotkey": args.winner_hotkey,
        "dry_run": args.dry_run
    })
    
    if args.dry_run:
        logger.info("DRY RUN - Would promote winner as baseline with:", extra={
            "tournament_id": args.tournament_id,
            "image_type": args.image_type,
            "winner_hotkey": args.winner_hotkey,
            "actions": [
                "1. Fork winner repository",
                "2. Build new baseline Docker image",
                "3. Insert new baseline record (ACTIVE)",
                "4. Deprecate old baseline"
            ]
        })
        return
    
    context = TournamentTaskContext(
        tournament_id=args.tournament_id,
        image_type=args.image_type,
        test_date=None,
        winner_hotkey=args.winner_hotkey
    )
    
    task = BaselinePromotionTask()
    
    try:
        result = task.execute_task(context)
        
        if result.get('status') == 'success':
            logger.info("Baseline promotion completed", extra=result)
        elif result.get('status') == 'skipped':
            logger.info("Baseline promotion skipped", extra=result)
        else:
            logger.warning("Baseline promotion issue", extra=result)
            sys.exit(1)
            
    except Exception as e:
        logger.error("Baseline promotion failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()