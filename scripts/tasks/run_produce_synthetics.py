#!/usr/bin/env python3
from dotenv import load_dotenv
from packages.jobs.tasks.produce_synthetics_task import ProduceSyntheticsTask
from packages.jobs.base.task_models import BaseTaskContext
import argparse


def main():
    parser = argparse.ArgumentParser(description='Produce Chain Synthetics Task')
    parser.add_argument('--network', required=True, help='Network name')
    parser.add_argument('--window-days', type=int, required=True, help='Time window in days')
    parser.add_argument('--processing-date', required=True, help='Processing date (YYYY-MM-DD)')
    args = parser.parse_args()

    load_dotenv()

    context = BaseTaskContext(
        network=args.network,
        window_days=args.window_days,
        processing_date=args.processing_date,
        #batch_size=args.batch_size
    )

    task = ProduceSyntheticsTask()
    task.execute_task(context)


if __name__ == "__main__":
    main()