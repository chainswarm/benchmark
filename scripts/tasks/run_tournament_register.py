import argparse
import sys
from datetime import datetime
from uuid import UUID

from dotenv import load_dotenv
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params

from packages.benchmark.managers.tournament_manager import TournamentManager
from packages.benchmark.models.miner import ImageType, Miner, MinerStatus
from packages.benchmark.models.tournament import TournamentStatus
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.tournament_repository import TournamentRepository


def main():
    parser = argparse.ArgumentParser(
        description='Register a miner for an active tournament.'
    )
    parser.add_argument(
        '--tournament-id',
        required=True,
        help='Tournament UUID to register for'
    )
    parser.add_argument(
        '--hotkey',
        required=True,
        help='Miner hotkey'
    )
    parser.add_argument(
        '--github-repository',
        required=True,
        help='Miner GitHub repository URL'
    )
    parser.add_argument(
        '--docker-image-tag',
        required=False,
        help='Docker image tag (defaults to {image_type}_{hotkey}_{short_hash})'
    )
    parser.add_argument(
        '--miner-database-name',
        required=False,
        help='Miner database name (defaults to miner_{hotkey})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be registered without registering'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    tournament_id = UUID(args.tournament_id)
    
    logger.info("Registering miner for tournament", extra={
        "tournament_id": str(tournament_id),
        "hotkey": args.hotkey,
        "github_repository": args.github_repository,
        "dry_run": args.dry_run
    })
    
    connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
    client_factory = ClientFactory(connection_params)
    
    with client_factory.client_context() as client:
        tournament_repo = TournamentRepository(client)
        tournament_manager = TournamentManager()
        
        tournament = tournament_repo.get_tournament_by_id(tournament_id)
        
        if not tournament:
            logger.error("Tournament not found", extra={"tournament_id": str(tournament_id)})
            sys.exit(1)
        
        if tournament.status != TournamentStatus.REGISTRATION:
            logger.error("Tournament not in registration phase", extra={
                "tournament_id": str(tournament_id),
                "status": tournament.status.value
            })
            sys.exit(1)
        
        existing = tournament_repo.get_participant(tournament_id, args.hotkey)
        if existing:
            logger.error("Miner already registered", extra={
                "tournament_id": str(tournament_id),
                "hotkey": args.hotkey
            })
            sys.exit(1)
        
        participants = tournament_repo.get_participants(tournament_id)
        if len(participants) >= tournament.max_participants:
            logger.error("Tournament is full", extra={
                "tournament_id": str(tournament_id),
                "max_participants": tournament.max_participants,
                "current_participants": len(participants)
            })
            sys.exit(1)
        
        registration_order = tournament_repo.get_next_registration_order(tournament_id)
        
        docker_image_tag = args.docker_image_tag or f"{tournament.image_type.value}_{args.hotkey[:8]}"
        miner_database_name = args.miner_database_name or f"miner_{args.hotkey[:16]}"
        
        if args.dry_run:
            logger.info("DRY RUN - Would register miner with:", extra={
                "tournament_id": str(tournament_id),
                "hotkey": args.hotkey,
                "registration_order": registration_order,
                "github_repository": args.github_repository,
                "docker_image_tag": docker_image_tag,
                "miner_database_name": miner_database_name
            })
            return
        
        try:
            miner = Miner(
                hotkey=args.hotkey,
                image_type=tournament.image_type,
                github_repository=args.github_repository,
                registered_at=datetime.now(),
                last_updated_at=datetime.now(),
                status=MinerStatus.ACTIVE
            )
            
            participant = tournament_manager.create_miner_participant(
                tournament=tournament,
                miner=miner,
                registration_order=registration_order,
                docker_image_tag=docker_image_tag,
                miner_database_name=miner_database_name
            )
            
            tournament_repo.insert_participant(participant)
            
            logger.info("Miner registered successfully", extra={
                "tournament_id": str(tournament_id),
                "hotkey": args.hotkey,
                "registration_order": registration_order
            })
            
        except Exception as e:
            logger.error("Failed to register miner", extra={"error": str(e)})
            sys.exit(1)


if __name__ == "__main__":
    main()