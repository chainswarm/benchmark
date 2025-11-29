import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.docker_build_task import DockerBuildTask


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hotkey', required=True, help='Miner hotkey')
    parser.add_argument('--image-type', required=True, choices=['analytics', 'ml'], help='Image type')
    args = parser.parse_args()
    
    load_dotenv()
    
    repos_base_path = os.getenv('BENCHMARK_REPOS_PATH', '/var/benchmark/repos')
    repository_path = Path(repos_base_path) / args.image_type / args.hotkey
    
    context = {
        'repository_path': str(repository_path),
        'hotkey': args.hotkey,
        'image_type': args.image_type
    }
    
    task = DockerBuildTask()
    result = task.execute_task(context)
    
    logger.info("Docker build completed", extra=result)


if __name__ == "__main__":
    main()