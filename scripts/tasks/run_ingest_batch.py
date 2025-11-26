#!/usr/bin/env python3
import os
import argparse
from dotenv import load_dotenv
from loguru import logger

from packages.jobs.tasks.ingest_batch_task import IngestBatchTask
from packages.jobs.base.task_models import BaseTaskContext

def main():
    parser = argparse.ArgumentParser(description='Manual Batch Ingestion Task')
    parser.add_argument('--network', required=True, help='Network name (e.g. torus)')
    parser.add_argument('--window-days', type=int, default=7, help='Time window in days')
    parser.add_argument('--processing-date', required=True, help='Processing date (YYYY-MM-DD)')
    parser.add_argument('--source', choices=['HTTP', 'S3', 'CLICKHOUSE'], help='Override ingestion source type')
    
    args = parser.parse_args()
    
    load_dotenv()
    
    if args.source:
        os.environ['INGESTION_SOURCE_TYPE'] = args.source
        logger.debug(f"Overriding INGESTION_SOURCE_TYPE to {args.source}")
    
    context = BaseTaskContext(
        network=args.network,
        window_days=args.window_days,
        processing_date=args.processing_date
    )
    
    print(f"Starting IngestBatchTask for {args.network} on {args.processing_date} (Window: {args.window_days}d)")
    task = IngestBatchTask()
    result = task.execute_task(context)
    print(f"Task Result: {result}")

if __name__ == "__main__":
    main()