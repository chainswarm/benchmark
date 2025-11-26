import os
from loguru import logger
from celery_singleton import Singleton
from dotenv import load_dotenv

from packages.jobs.celery_app import celery_app
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.jobs.base.task_models import BaseTaskContext
from packages.storage.repositories import get_connection_params, ClientFactory
from packages import setup_logger
from packages.ingestion.service import IngestionService

class IngestBatchTask(BaseDataPipelineTask, Singleton):

    def execute_task(self, context: BaseTaskContext):
        service_name = f'ingest-{context.network}-batch'
        setup_logger(service_name)

        ingestion_source = os.getenv('INGESTION_SOURCE_TYPE', 'DIRECTORY')
        
        logger.info(
            "Starting batch ingestion",
            extra={
                "network": context.network,
                "window_days": context.window_days,
                "processing_date": context.processing_date,
                "source": ingestion_source
            }
        )

        connection_params = get_connection_params(context.network)
        connection_params['database'] = f"synthetics_{context.network}"
        client_factory = ClientFactory(connection_params)

        with client_factory.client_context() as client:
            service = IngestionService(client, ingestion_source)
            service.run(context.network, context.processing_date, context.window_days)

@celery_app.task(
    bind=True,
    base=IngestBatchTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 5,
        'countdown': 60
    },
    time_limit=3600,
    soft_time_limit=3500
)
def ingest_batch_task(
    self,
    network: str,
    window_days: int,
    processing_date: str
):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date
    )
    
    return self.run(context)