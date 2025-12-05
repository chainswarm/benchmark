from pathlib import Path
from typing import Optional

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.models.miner import ImageType
from packages.jobs.base import BenchmarkTaskContext
from packages.jobs.celery_app import celery_app


class ContainerRunTask(BaseTask, Singleton):

    def execute_task(self, context: BenchmarkTaskContext) -> dict:
        image_tag = context.image_tag
        data_mount_path = Path(context.data_mount_path)
        miner_database = context.miner_database
        timeout = context.timeout or 3600
        hotkey = context.hotkey
        image_type = ImageType(context.image_type)
        
        logger.info("Starting container run", extra={
            "image_tag": image_tag,
            "data_mount_path": str(data_mount_path),
            "miner_database": miner_database,
            "timeout": timeout,
            "hotkey": hotkey,
            "image_type": image_type.value,
            "network": context.network
        })
        
        if not data_mount_path.exists():
            raise ValueError(f"Data mount path does not exist: {data_mount_path}")
        
        docker_manager = DockerManager()
        
        if not docker_manager.image_exists(image_tag):
            raise ValueError(f"Docker image not found: {image_tag}")
        
        container_result = docker_manager.run_container(
            image_tag=image_tag,
            data_mount=data_mount_path,
            miner_database=miner_database,
            timeout=timeout,
            network_mode="none"
        )
        
        success = container_result.exit_code == 0 and not container_result.timed_out
        
        logger.info("Container execution completed", extra={
            "hotkey": hotkey,
            "image_type": image_type.value,
            "image_tag": image_tag,
            "success": success,
            "exit_code": container_result.exit_code,
            "execution_time_seconds": container_result.execution_time_seconds,
            "timed_out": container_result.timed_out,
            "gpu_memory_peak_mb": container_result.gpu_memory_peak_mb
        })
        
        return {
            "success": success,
            "hotkey": hotkey,
            "image_type": image_type.value,
            "image_tag": image_tag,
            "exit_code": container_result.exit_code,
            "execution_time_seconds": container_result.execution_time_seconds,
            "timed_out": container_result.timed_out,
            "gpu_memory_peak_mb": container_result.gpu_memory_peak_mb,
            "logs": container_result.logs[:10000] if container_result.logs else "",
        }


@celery_app.task(
    bind=True,
    base=ContainerRunTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 1,
        'countdown': 120
    },
    time_limit=4500,
    soft_time_limit=4200
)
def container_run_task(
    self,
    network: str,
    window_days: int,
    processing_date: str,
    image_tag: str,
    data_mount_path: str,
    miner_database: str,
    hotkey: str,
    image_type: str,
    timeout: Optional[int] = 3600,
):
    context = BenchmarkTaskContext(
        network=network,
        window_days=window_days,
        processing_date=processing_date,
        image_tag=image_tag,
        data_mount_path=data_mount_path,
        miner_database=miner_database,
        hotkey=hotkey,
        image_type=image_type,
        timeout=timeout or 3600
    )
    
    return self.run(context)