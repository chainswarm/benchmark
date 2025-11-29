from celery_singleton import Singleton
from loguru import logger
from chainswarm_core.jobs import BaseTask
from chainswarm_core.observability import setup_logger
from packages.jobs.celery_app import celery_app
from packages.storage.repositories import get_connection_params, ClientFactory, MigrateSchema
from packages.benchmark.models.miner import ImageType


class MinerDatabaseInitializationTask(BaseTask, Singleton):

    def execute_task(self, context: dict):
        hotkey = context['hotkey']
        image_type = ImageType(context['image_type'])
        
        service_name = f'miner-db-init-{hotkey}'
        setup_logger(service_name)

        connection_params = get_connection_params(hotkey)
        
        logger.info(f"Initializing {image_type.value} miner database for {hotkey}")
        
        client_factory = ClientFactory(connection_params)
        with client_factory.client_context() as client:
            migrate_schema = MigrateSchema(client)
            migrate_schema.run_miner_schema_migrations(image_type.value)
            
            logger.info(f"Miner database schema initialization completed for {hotkey}")
            
            return {
                "hotkey": hotkey,
                "image_type": image_type.value,
                "database_name": connection_params['database']
            }


@celery_app.task(
    bind=True,
    base=MinerDatabaseInitializationTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 60
    },
    time_limit=1800,
    soft_time_limit=1700
)
def miner_database_initialization_task(
    self,
    hotkey: str,
    image_type: str,
):
    context = {
        'hotkey': hotkey,
        'image_type': image_type
    }
    
    return self.run(context)