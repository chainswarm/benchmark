from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask, BaseTaskContext
from chainswarm_core.observability import setup_logger

from packages.jobs.celery_app import celery_app
from packages.storage.repositories import get_connection_params, ClientFactory, MigrateSchema, create_database


class BenchmarkInitializationTask(BaseTask, Singleton):

    def execute_task(self, context: BaseTaskContext):
        setup_logger('benchmark-initialization')

        connection_params = get_connection_params('default')
        connection_params['database'] = 'benchmark'
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
def benchmark_initialization_task(self):
    context = BaseTaskContext()
    return self.run(context)