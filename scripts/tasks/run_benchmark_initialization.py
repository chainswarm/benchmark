#!/usr/bin/env python3
import argparse
from datetime import date
from dotenv import load_dotenv

from chainswarm_core.observability import setup_logger
from chainswarm_core.jobs import BaseTaskContext

from packages.jobs.tasks.benchmark_initialization_task import BenchmarkInitializationTask


def main():
    parser = argparse.ArgumentParser(description='Benchmark Initialization Task')
    parser.add_argument('--network', default='default', help='Network name (default: default)')
    parser.add_argument('--window-days', type=int, default=7, help='Time window in days')
    parser.add_argument('--processing-date', default=None, help='Processing date (YYYY-MM-DD)')
    args = parser.parse_args()
    
    load_dotenv()
    
    # Setup logger once for the task
    service_name = f'benchmark-{args.network}-initialization'
    setup_logger(service_name)
    
    processing_date = args.processing_date or date.today().isoformat()
    
    context = BaseTaskContext(
        network=args.network,
        window_days=args.window_days,
        processing_date=processing_date
    )
    
    task = BenchmarkInitializationTask()
    task.execute_task(context)


if __name__ == "__main__":
    main()