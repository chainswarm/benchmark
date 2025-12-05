from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.repository_manager import RepositoryManager
from packages.benchmark.models.miner import ImageType
from packages.jobs.base import BenchmarkTaskContext
from packages.jobs.celery_app import celery_app


class RepositoryCloneTask(BaseTask, Singleton):

    def execute_task(self, context: BenchmarkTaskContext) -> dict:
        github_url = context.github_repository
        hotkey = context.hotkey
        image_type = ImageType(context.image_type)
        
        logger.info("Starting repository clone", extra={
            "github_url": github_url,
            "hotkey": hotkey,
            "image_type": image_type.value
        })
        
        repository_manager = RepositoryManager()
        
        clone_result = repository_manager.clone_with_type(
            hotkey=hotkey,
            repository_url=github_url,
            image_type=image_type
        )
        
        if clone_result.success:
            logger.info("Repository cloned successfully", extra={
                "hotkey": hotkey,
                "image_type": image_type.value,
                "repository_path": str(clone_result.repository_path)
            })
        else:
            logger.error("Repository clone failed", extra={
                "hotkey": hotkey,
                "image_type": image_type.value,
                "error": clone_result.error_message
            })
        
        return clone_result.to_dict()


@celery_app.task(
    bind=True,
    base=RepositoryCloneTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 60
    },
    time_limit=600,
    soft_time_limit=550
)
def repository_clone_task(
    self,
    github_repository: str,
    hotkey: str,
    image_type: str,
):
    context = BenchmarkTaskContext(
        github_repository=github_repository,
        hotkey=hotkey,
        image_type=image_type
    )
    
    return self.run(context)