from datetime import date, datetime
from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import RunStatus
from packages.jobs.celery_app import celery_app


class BenchmarkTestExecutionTask(BaseTask, Singleton):

    def execute_task(self, context: dict):
        epoch_id = UUID(context['epoch_id'])
        hotkey = context['hotkey']
        image_type = ImageType(context['image_type'])
        test_date = date.fromisoformat(context['test_date'])
        network = context['network']
        window_days = context['window_days']
        processing_date = date.fromisoformat(context['processing_date'])
        
        logger.info("Starting test execution", extra={
            "epoch_id": str(epoch_id),
            "hotkey": hotkey,
            "network": network,
            "window_days": window_days
        })
        
        from packages.storage.repositories.benchmark_results_repository import BenchmarkResultsRepository
        from packages.storage.repositories.benchmark_epoch_repository import BenchmarkEpochRepository
        
        results_repo = BenchmarkResultsRepository()
        epoch_repo = BenchmarkEpochRepository()
        
        epoch = epoch_repo.get_epoch_by_id(epoch_id)
        
        docker_manager = DockerManager()
        dataset_manager = DatasetManager()
        
        dataset_path = dataset_manager.fetch_dataset(network, str(processing_date), window_days)
        mount_path = dataset_manager.prepare_miner_mount(dataset_path)
        
        run_id = results_repo.create_run(
            epoch_id=epoch_id,
            hotkey=hotkey,
            image_type=image_type,
            test_date=test_date,
            network=network,
            window_days=window_days,
            processing_date=processing_date
        )
        
        results_repo.update_run_status(run_id, image_type, RunStatus.RUNNING)
        
        try:
            container_result = docker_manager.run_container(
                image_tag=epoch.docker_image_tag,
                data_mount=mount_path,
                miner_database=epoch.miner_database_name
            )
            
            if container_result.timed_out:
                results_repo.update_run_status(run_id, image_type, RunStatus.TIMEOUT)
                results_repo.update_run_execution_metrics(
                    run_id=run_id,
                    image_type=image_type,
                    execution_time=container_result.execution_time_seconds,
                    exit_code=container_result.exit_code,
                    gpu_memory_peak=container_result.gpu_memory_peak_mb
                )
                return {
                    "status": "timeout",
                    "run_id": str(run_id),
                    "execution_time": container_result.execution_time_seconds
                }
            
            if container_result.exit_code != 0:
                results_repo.update_run_status(
                    run_id,
                    image_type,
                    RunStatus.FAILED,
                    error_message=f"Container exited with code {container_result.exit_code}"
                )
                results_repo.update_run_execution_metrics(
                    run_id=run_id,
                    image_type=image_type,
                    execution_time=container_result.execution_time_seconds,
                    exit_code=container_result.exit_code,
                    gpu_memory_peak=container_result.gpu_memory_peak_mb
                )
                return {
                    "status": "failed",
                    "run_id": str(run_id),
                    "exit_code": container_result.exit_code
                }
            
            results_repo.update_run_execution_metrics(
                run_id=run_id,
                image_type=image_type,
                execution_time=container_result.execution_time_seconds,
                exit_code=container_result.exit_code,
                gpu_memory_peak=container_result.gpu_memory_peak_mb
            )
            
            from packages.jobs.tasks.benchmark_validation_task import benchmark_validation_task
            
            benchmark_validation_task.delay(
                run_id=str(run_id),
                epoch_id=str(epoch_id),
                hotkey=hotkey,
                image_type=image_type.value,
                network=network,
                window_days=window_days,
                processing_date=str(processing_date),
                miner_database=epoch.miner_database_name
            )
            
            return {
                "status": "success",
                "run_id": str(run_id),
                "execution_time": container_result.execution_time_seconds
            }
            
        except Exception as e:
            logger.error("Test execution failed", extra={
                "run_id": str(run_id),
                "error": str(e)
            })
            results_repo.update_run_status(
                run_id,
                image_type,
                RunStatus.FAILED,
                error_message=str(e)
            )
            raise


@celery_app.task(
    bind=True,
    base=BenchmarkTestExecutionTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=4500,
    soft_time_limit=4200
)
def benchmark_test_execution_task(
    self,
    epoch_id: str,
    hotkey: str,
    image_type: str,
    test_date: str,
    network: str,
    window_days: int,
    processing_date: str,
):
    context = {
        'epoch_id': epoch_id,
        'hotkey': hotkey,
        'image_type': image_type,
        'test_date': test_date,
        'network': network,
        'window_days': window_days,
        'processing_date': processing_date
    }
    
    return self.run(context)