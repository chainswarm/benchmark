from celery_singleton import Singleton
from packages.jobs.base.task_models import BaseTaskContext
from packages.jobs.celery_app import celery_app
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.storage.repositories import get_connection_params, ClientFactory, MigrateSchema
from packages import setup_logger


class InitializeSyntheticsTask(BaseDataPipelineTask, Singleton):

    def execute_task(self, context: BaseTaskContext):
        service_name = f'synthetics-{context.network}-initialize'
        setup_logger(service_name)

        connection_params = get_connection_params(context.network)
        
        from packages.storage.repositories import create_database
        create_database(connection_params)

        client_factory = ClientFactory(connection_params)
        with client_factory.client_context() as client:
            migrate_schema = MigrateSchema(client)
            migrate_schema.run_core_migrations()
            migrate_schema.run_synthetics_migrations()


@celery_app.task(
    bind=True,
    base=InitializeSyntheticsTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 24,
        'countdown': 600
    },
    time_limit=7200,
    soft_time_limit=7080
)
def initialize_analyzers_task(self, network: str, window_days: int, processing_date: str):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date
    )

    return self.run(context)

