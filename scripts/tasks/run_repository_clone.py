import argparse
from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.repository_clone_task import RepositoryCloneTask


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--github-url', required=True, help='GitHub repository URL')
    parser.add_argument('--hotkey', required=True, help='Miner hotkey')
    parser.add_argument('--image-type', required=True, choices=['analytics', 'ml'], help='Image type')
    args = parser.parse_args()
    
    load_dotenv()
    
    context = {
        'github_url': args.github_url,
        'hotkey': args.hotkey,
        'image_type': args.image_type
    }
    
    task = RepositoryCloneTask()
    result = task.execute_task(context)
    
    logger.info("Repository clone completed", extra=result)


if __name__ == "__main__":
    main()