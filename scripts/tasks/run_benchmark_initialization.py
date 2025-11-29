import argparse
from dotenv import load_dotenv
from loguru import logger

from packages.jobs.base.task_models import BenchmarkTaskContext
from packages.jobs.tasks.benchmark_initialization_task import BenchmarkInitializationTask


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    
    load_dotenv()
    
    context = BenchmarkTaskContext()
    
    task = BenchmarkInitializationTask()
    task.execute_task(context)
    
    logger.info("Benchmark schema initialization completed")


if __name__ == "__main__":
    main()