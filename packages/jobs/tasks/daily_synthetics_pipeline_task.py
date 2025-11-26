from datetime import datetime
from loguru import logger
from celery_singleton import Singleton

from packages.jobs.celery_app import celery_app
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.jobs.base.task_models import BaseTaskContext

# Import sub-tasks
from packages.jobs.tasks.ingest_batch_task import IngestBatchTask
from packages.jobs.tasks.initialize_synthetics_task import InitializeSyntheticsTask
from packages.jobs.tasks.log_computation_audit_task import LogComputationAuditTask
from packages.jobs.tasks.produce_synthetics_task import ProduceSyntheticsTask
from packages.jobs.tasks.export_batch_task import ExportBatchTask


class DailySyntheticsTask(BaseDataPipelineTask, Singleton):

    
    def execute_task(self, context: BaseTaskContext):
        processing_date = context.processing_date
        network = context.network
        
        logger.info(f"Starting Chain Synthetics for {network} on {processing_date}")
        
        try:
            logger.info("Initializing Analyzers Schema")
            InitializeSyntheticsTask().execute_task(context)

            logger.info("Ingesting Batch Data")
            IngestBatchTask().execute_task(context)

            logger.info("Injecting Synthetic Patterns (Algorithmic & Real World)")
            ProduceSyntheticsTask().execute_task(context)

            logger.info("Logging Computation Audit")
            
            # Create audit context with start time
            audit_context = BaseTaskContext(
                network=network,
                window_days=context.window_days,
                processing_date=processing_date
            )

            audit_context.pipeline_started_at = datetime.now()
            LogComputationAuditTask().execute_task(audit_context)
            
            logger.info("Exporting Batch to S3")
            ExportBatchTask().execute_task(context)
            
            logger.success(f"Chain Synthetics completed successfully for {network} on {processing_date}")
            return {
                "status": "success",
                "network": network,
                "date": processing_date
            }

        except Exception as e:
            logger.error(f"Chain Synthetics failed: {str(e)}")
            raise e


@celery_app.task(
    bind=True,
    base=DailySyntheticsTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 300
    },
    time_limit=14400, # 4 hours
    soft_time_limit=14000
)
def daily_synthetic_pipeline_task(
    self,
    network: str,
    window_days: int,
    processing_date: str,
    batch_size: int = 1000,
):
    context = BaseTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date,
        batch_size=batch_size
    )

    return self.run(context)