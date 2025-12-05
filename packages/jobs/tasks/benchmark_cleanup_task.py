from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core import ClientFactory
from chainswarm_core.db import get_connection_params
from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.managers.repository_manager import RepositoryManager
from packages.benchmark.models.miner import ImageType
from packages.jobs.base import BenchmarkTaskContext
from packages.jobs.celery_app import celery_app
from packages.storage import DATABASE_PREFIX
from packages.storage.repositories.benchmark_epoch_repository import BenchmarkEpochRepository
from packages.storage.repositories.miner_database_repository import MinerDatabaseRepository


class BenchmarkCleanupTask(BaseTask, Singleton):

    def execute_task(self, context: BenchmarkTaskContext):
        epoch_id = UUID(context.epoch_id)
        hotkey = context.hotkey
        image_type = ImageType(context.image_type)
        
        logger.info("Starting cleanup", extra={
            "epoch_id": str(epoch_id),
            "hotkey": hotkey,
            "image_type": image_type.value
        })

        connection_params = get_connection_params(context.network, database_prefix=DATABASE_PREFIX)
        client_factory = ClientFactory(connection_params)
        docker_manager = DockerManager()
        repo_manager = RepositoryManager()
        
        with client_factory.client_context() as client:
            epoch_repo = BenchmarkEpochRepository(client)
            db_repo = MinerDatabaseRepository(client)
            
            epoch = epoch_repo.get_epoch_by_id(epoch_id)
        
            try:
                docker_manager.remove_image(epoch.docker_image_tag)
                logger.info("Removed Docker image", extra={
                    "image_tag": epoch.docker_image_tag
                })
            except Exception as e:
                logger.warning("Failed to remove Docker image", extra={
                    "image_tag": epoch.docker_image_tag,
                    "error": str(e)
                })
            
            try:
                repo_manager.cleanup_repository(hotkey)
                logger.info("Cleaned up repository", extra={
                    "hotkey": hotkey
                })
            except Exception as e:
                logger.warning("Failed to cleanup repository", extra={
                    "hotkey": hotkey,
                    "error": str(e)
                })
            
            db_repo.update_database_status(
                hotkey=hotkey,
                image_type=image_type,
                status='archived'
            )
            
            logger.info("Cleanup completed", extra={
                "epoch_id": str(epoch_id),
                "hotkey": hotkey
            })
            
            return {
                "status": "success",
                "epoch_id": str(epoch_id),
                "hotkey": hotkey
            }


@celery_app.task(
    bind=True,
    base=BenchmarkCleanupTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=600,
    soft_time_limit=550
)
def benchmark_cleanup_task(
    self,
    network: str,
    window_days: int,
    processing_date: str,
    epoch_id: str,
    hotkey: str,
    image_type: str,
):
    context = BenchmarkTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date,
        epoch_id=epoch_id,
        hotkey=hotkey,
        image_type=image_type
    )
    
    return self.run(context)