#!/usr/bin/env python3
from dotenv import load_dotenv
from packages.jobs.base.task_models import BaseTaskContext
import argparse

from packages.jobs.tasks import InitializeSyntheticsTask


def main():
    parser = argparse.ArgumentParser(description='Initialize Synthetics Task')
    parser.add_argument('--network', required=True, help='Network name')
    args = parser.parse_args()
    
    load_dotenv()
    
    context = BaseTaskContext(
        network=args.network
    )
    
    task = InitializeSyntheticsTask()
    task.execute_task(context)


if __name__ == "__main__":
    main()