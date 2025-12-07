import argparse
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params

from packages.benchmark.managers.tournament_manager import TournamentManager
from packages.benchmark.models.miner import ImageType
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.baseline_repository import BaselineRepository
from packages.storage.repositories.tournament_repository import TournamentRepository


def main():
    parser = argparse.ArgumentParser(
        description='Create a new tournament with the current active baseline.'
    )
    parser.add_argument(
        '--name',
        required=True,
        help='Tournament name'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images'
    )
    parser.add_argument(
        '--registration-start',
        required=False,
        help='Registration start date (YYYY-MM-DD). Defaults to today.'
    )
    parser.add_argument(
        '--registration-end',
        required=False,
        help='Registration end date (YYYY-MM-DD). Defaults to +7 days from start.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without creating'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    image_type = ImageType(args.image_type)
    
    reg_start = date.fromisoformat(args.registration_start) if args.registration_start else date.today()
    reg_end = date.fromisoformat(args.registration_end) if args.registration_end else (reg_start + timedelta(days=7))
    
    logger.info("Creating tournament", extra={
        "name": args.name,
        "image_type": args.image_type,
        "registration_start": str(reg_start),
        "registration_end": str(reg_end),
        "dry_run": args.dry_run
    })
    
    connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
    client_factory = ClientFactory(connection_params)
    
    with client_factory.client_context() as client:
        baseline_repo = BaselineRepository(client)
        tournament_repo = TournamentRepository(client)
        tournament_manager = TournamentManager()
        
        baseline = baseline_repo.get_active_baseline(image_type)
        
        if not baseline:
            logger.error("No active baseline found for image type", extra={"image_type": args.image_type})
            sys.exit(1)
        
        logger.info("Using baseline", extra={
            "baseline_id": str(baseline.baseline_id),
            "version": baseline.version,
            "docker_image_tag": baseline.docker_image_tag
        })
        
        if args.dry_run:
            competition_start = reg_end + timedelta(days=1)
            competition_end = competition_start + timedelta(days=tournament_manager.epoch_days - 1)
            
            logger.info("DRY RUN - Would create tournament with:", extra={
                "name": args.name,
                "image_type": args.image_type,
                "baseline_version": baseline.version,
                "registration_start": str(reg_start),
                "registration_end": str(reg_end),
                "competition_start": str(competition_start),
                "competition_end": str(competition_end),
                "epoch_days": tournament_manager.epoch_days,
                "max_participants": tournament_manager.max_participants,
                "test_networks": tournament_manager.test_networks,
                "test_window_days": tournament_manager.test_window_days
            })
            return
        
        try:
            tournament = tournament_manager.create_tournament(
                name=args.name,
                image_type=image_type,
                baseline=baseline,
                registration_start=reg_start,
                registration_end=reg_end
            )
            
            tournament_repo.insert_tournament(tournament)
            
            baseline_participant = tournament_manager.create_baseline_participant(
                tournament=tournament,
                baseline=baseline
            )
            
            tournament_repo.insert_participant(baseline_participant)
            
            logger.info("Tournament created successfully", extra={
                "tournament_id": str(tournament.tournament_id),
                "name": tournament.name,
                "baseline_participant": baseline_participant.hotkey,
                "registration_start": str(tournament.registration_start),
                "registration_end": str(tournament.registration_end),
                "competition_start": str(tournament.competition_start),
                "competition_end": str(tournament.competition_end)
            })
            
        except Exception as e:
            logger.error("Failed to create tournament", extra={"error": str(e)})
            sys.exit(1)


if __name__ == "__main__":
    main()