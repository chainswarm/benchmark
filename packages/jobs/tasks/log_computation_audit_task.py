from datetime import datetime
from loguru import logger
from celery_singleton import Singleton

from packages.jobs.base import BaseTaskContext
from packages.jobs.celery_app import celery_app
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.storage.repositories import get_connection_params, ClientFactory
from packages.storage.repositories.computation_audit_repository import ComputationAuditRepository
from packages import setup_logger


class LogComputationAuditTask(BaseDataPipelineTask, Singleton):

    def execute_task(self, context: BaseTaskContext):
        service_name = f'audit-{context.network}-log-completion'
        setup_logger(service_name)

        connection_params = get_connection_params(context.network)
        client_factory = ClientFactory(connection_params)
        
        with client_factory.client_context() as client:
            computation_audit_repository = ComputationAuditRepository(client)
            
            computation_audit_repository.log_completion(
                window_days=context.window_days,
                processing_date=context.processing_date,
                created_at=context.pipeline_started_at,
                end_at=datetime.now()
            )
            
            logger.info(
                "Logged computation audit",
                extra={
                    "network": context.network,
                    "window_days": context.window_days,
                    "processing_date": context.processing_date
                }
            )


@celery_app.task(
    bind=True,
    base=LogComputationAuditTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 60
    },
    time_limit=300,
    soft_time_limit=280
)
def log_computation_audit_task(
    self,
    network: str,
    window_days: int,
    processing_date: str,
    pipeline_started_at: datetime
):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date
    )
    context.pipeline_started_at = pipeline_started_at
    
    return self.run(context)