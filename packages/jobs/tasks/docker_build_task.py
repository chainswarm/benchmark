import time
from pathlib import Path

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.managers.repository_manager import RepositoryManager
from packages.benchmark.models.analysis import BuildResult
from packages.benchmark.models.miner import ImageType
from packages.jobs.base import BenchmarkTaskContext
from packages.jobs.celery_app import celery_app


class DockerBuildTask(BaseTask, Singleton):

    def execute_task(self, context: BenchmarkTaskContext) -> dict:
        repository_path = Path(context.repository_path)
        hotkey = context.hotkey
        image_type = ImageType(context.image_type)
        
        logger.info("Starting Docker build", extra={
            "repository_path": str(repository_path),
            "hotkey": hotkey,
            "image_type": image_type.value,
            "network": context.network
        })
        
        start_time = time.time()
        
        if not repository_path.exists():
            raise ValueError(f"Repository path does not exist: {repository_path}")
        
        dockerfile_path = repository_path / "ops/Dockerfile"
        if not dockerfile_path.exists():
            raise ValueError("Dockerfile not found in repository")
        
        repo_manager = RepositoryManager()
        commit_hash = repo_manager.get_commit_hash(repository_path)
        
        logger.info("Retrieved commit hash", extra={
            "hotkey": hotkey,
            "commit_hash": commit_hash
        })
        
        docker_manager = DockerManager()
        
        image_tag = docker_manager.build_image(
            repo_path=repository_path,
            image_type=image_type.value,
            hotkey=hotkey,
            commit_hash=commit_hash
        )
        
        build_time = time.time() - start_time
        
        logger.info("Docker build completed", extra={
            "hotkey": hotkey,
            "image_type": image_type.value,
            "image_tag": image_tag,
            "build_time_seconds": build_time
        })
        
        return BuildResult(
            success=True,
            image_tag=image_tag,
            build_time_seconds=build_time,
            hotkey=hotkey,
            image_type=image_type.value
        ).to_dict()


@celery_app.task(
    bind=True,
    base=DockerBuildTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 120
    },
    time_limit=3600,
    soft_time_limit=3500
)
def docker_build_task(
    self,
    network: str,
    window_days: int,
    processing_date: str,
    repository_path: str,
    hotkey: str,
    image_type: str,
):
    context = BenchmarkTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date,
        repository_path=repository_path,
        hotkey=hotkey,
        image_type=image_type
    )
    
    return self.run(context)