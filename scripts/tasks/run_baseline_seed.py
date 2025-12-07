import argparse
import sys
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params

from packages.benchmark.models.baseline import Baseline, BaselineStatus
from packages.benchmark.models.miner import ImageType
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.baseline_repository import BaselineRepository


def main():
    parser = argparse.ArgumentParser(
        description='Seed the initial baseline for an image type.'
    )
    parser.add_argument(
        '--image-type',
        required=True,
        choices=['analytics', 'ml'],
        help='Type of miner images'
    )
    parser.add_argument(
        '--version',
        required=False,
        default='1.0.0',
        help='Baseline version (default: 1.0.0)'
    )
    parser.add_argument(
        '--github-repository',
        required=False,
        default='https://github.com/chainswarm/baseline',
        help='Baseline GitHub repository URL'
    )
    parser.add_argument(
        '--docker-image-tag',
        required=False,
        help='Docker image tag (defaults to baseline_{image_type}_{version})'
    )
    parser.add_argument(
        '--commit-hash',
        required=False,
        default='0000000',
        help='Commit hash for the baseline (default: 0000000)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without creating'
    )
    args = parser.parse_args()
    
    load_dotenv()
    
    image_type = ImageType(args.image_type)
    docker_image_tag = args.docker_image_tag or f"baseline_{args.image_type}_{args.version}"
    
    logger.info("Seeding baseline", extra={
        "image_type": args.image_type,
        "version": args.version,
        "github_repository": args.github_repository,
        "docker_image_tag": docker_image_tag,
        "dry_run": args.dry_run
    })
    
    connection_params = get_connection_params('torus', database_prefix=DATABASE_PREFIX)
    client_factory = ClientFactory(connection_params)
    
    with client_factory.client_context() as client:
        baseline_repo = BaselineRepository(client)
        
        existing = baseline_repo.get_active_baseline(image_type)
        if existing:
            logger.error("Active baseline already exists", extra={
                "baseline_id": str(existing.baseline_id),
                "version": existing.version
            })
            sys.exit(1)
        
        if args.dry_run:
            logger.info("DRY RUN - Would create baseline with:", extra={
                "image_type": args.image_type,
                "version": args.version,
                "github_repository": args.github_repository,
                "docker_image_tag": docker_image_tag,
                "status": "active"
            })
            return
        
        try:
            baseline = Baseline(
                baseline_id=uuid4(),
                image_type=image_type,
                version=args.version,
                github_repository=args.github_repository,
                commit_hash=args.commit_hash,
                docker_image_tag=docker_image_tag,
                status=BaselineStatus.ACTIVE,
                created_at=datetime.now(),
                activated_at=datetime.now(),
                deprecated_at=None,
                originated_from_hotkey=None,
                originated_from_tournament_id=None
            )
            
            baseline_repo.insert_baseline(baseline)
            
            logger.info("Baseline seeded successfully", extra={
                "baseline_id": str(baseline.baseline_id),
                "version": baseline.version,
                "docker_image_tag": baseline.docker_image_tag
            })
            
        except Exception as e:
            logger.error("Failed to seed baseline", extra={"error": str(e)})
            sys.exit(1)


if __name__ == "__main__":
    main()