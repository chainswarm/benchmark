from celery_singleton import Singleton
from loguru import logger

from chainswarm_core import ClientFactory, create_database
from chainswarm_core.db import get_connection_params
from chainswarm_core.jobs import BaseTask, BaseTaskContext

from packages.jobs.celery_app import celery_app
from packages.storage import MigrateSchema, DATABASE_PREFIX


class BenchmarkInitializationTask(BaseTask, Singleton):

    def execute_task(self, context: BaseTaskContext):
        connection_params = get_connection_params(context.network, database_prefix=DATABASE_PREFIX)
        create_database(connection_params)

        client_factory = ClientFactory(connection_params)
        with client_factory.client_context() as client:
            migrate_schema = MigrateSchema(client)
            migrate_schema.run_core_migrations()
            
            logger.info("Benchmark schema initialization completed")


@celery_app.task(
    bind=True,
    base=BenchmarkInitializationTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 60
    },
    time_limit=1800,
    soft_time_limit=1700
)
def benchmark_initialization_task(self, network: str, window_days: int, processing_date: str):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date
    )
    return self.run(context)