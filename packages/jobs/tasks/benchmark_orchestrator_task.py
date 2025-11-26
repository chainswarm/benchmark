from datetime import date, datetime, timedelta
from typing import List
from uuid import uuid4

from celery_singleton import Singleton
from loguru import logger

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.benchmark.managers.docker_manager import DockerManager
from packages.benchmark.managers.repository_manager import RepositoryManager
from packages.benchmark.managers.scoring_manager import ScoringManager
from packages.benchmark.managers.validation_manager import ValidationManager
from packages.benchmark.models.epoch import BenchmarkEpoch, EpochStatus
from packages.benchmark.models.miner import ImageType, Miner, MinerStatus
from packages.jobs.base.base_task import BaseDataPipelineTask
from packages.jobs.celery_app import celery_app


class BenchmarkOrchestratorTask(BaseDataPipelineTask, Singleton):

    def execute_task(self, context: dict):
        image_type = ImageType(context['image_type'])
        test_date = date.fromisoformat(context['test_date'])
        
        logger.info("Starting benchmark orchestrator", extra={
            "image_type": image_type.value,
            "test_date": str(test_date)
        })
        
        from packages.storage.repositories.miner_registry_repository import MinerRegistryRepository
        from packages.storage.repositories.benchmark_epoch_repository import BenchmarkEpochRepository
        
        miner_repo = MinerRegistryRepository()
        epoch_repo = BenchmarkEpochRepository()
        
        repo_manager = RepositoryManager()
        docker_manager = DockerManager()
        dataset_manager = DatasetManager()
        
        active_miners = miner_repo.get_active_miners(image_type)
        
        logger.info("Found active miners", extra={
            "count": len(active_miners),
            "image_type": image_type.value
        })
        
        for miner in active_miners:
            try:
                self._process_miner(
                    miner=miner,
                    test_date=test_date,
                    epoch_repo=epoch_repo,
                    repo_manager=repo_manager,
                    docker_manager=docker_manager,
                    dataset_manager=dataset_manager
                )
            except Exception as e:
                logger.error("Failed to process miner", extra={
                    "hotkey": miner.hotkey,
                    "error": str(e)
                })
                miner_repo.update_miner_status(
                    miner.hotkey,
                    miner.image_type,
                    MinerStatus.FAILED,
                    str(e)
                )
        
        return {
            "status": "success",
            "image_type": image_type.value,
            "test_date": str(test_date),
            "miners_processed": len(active_miners)
        }

    def _process_miner(
        self,
        miner: Miner,
        test_date: date,
        epoch_repo,
        repo_manager: RepositoryManager,
        docker_manager: DockerManager,
        dataset_manager: DatasetManager
    ):
        logger.info("Processing miner", extra={
            "hotkey": miner.hotkey,
            "image_type": miner.image_type.value
        })
        
        epoch = epoch_repo.get_active_epoch(miner.hotkey, miner.image_type)
        
        if epoch is None:
            epoch = self._create_new_epoch(
                miner=miner,
                start_date=test_date,
                epoch_repo=epoch_repo,
                repo_manager=repo_manager,
                docker_manager=docker_manager,
                dataset_manager=dataset_manager
            )
        
        if epoch.status == EpochStatus.FAILED:
            logger.warning("Skipping failed epoch", extra={
                "epoch_id": str(epoch.epoch_id),
                "hotkey": miner.hotkey
            })
            return
        
        self._run_daily_test(
            epoch=epoch,
            test_date=test_date,
            miner=miner
        )
        
        if self._is_epoch_complete(epoch, test_date):
            self._finalize_epoch(epoch, miner)

    def _create_new_epoch(
        self,
        miner: Miner,
        start_date: date,
        epoch_repo,
        repo_manager: RepositoryManager,
        docker_manager: DockerManager,
        dataset_manager: DatasetManager
    ) -> BenchmarkEpoch:
        logger.info("Creating new epoch", extra={
            "hotkey": miner.hotkey,
            "start_date": str(start_date)
        })
        
        repo_path = repo_manager.clone_or_pull(miner.hotkey, miner.github_repository)
        
        validation_result = repo_manager.validate_repository(repo_path)
        
        if not validation_result.is_valid:
            logger.error("Repository validation failed", extra={
                "hotkey": miner.hotkey,
                "error": validation_result.error_message
            })
            raise ValueError(validation_result.error_message)
        
        image_tag = docker_manager.build_image(repo_path, miner.image_type.value, miner.hotkey)
        
        database_name = dataset_manager.create_miner_database(miner.hotkey, miner.image_type)
        
        epoch_id = uuid4()
        end_date = start_date + timedelta(days=6)
        
        epoch = BenchmarkEpoch(
            epoch_id=epoch_id,
            hotkey=miner.hotkey,
            image_type=miner.image_type,
            start_date=start_date,
            end_date=end_date,
            status=EpochStatus.RUNNING,
            docker_image_tag=image_tag,
            miner_database_name=database_name,
            created_at=datetime.now(),
            completed_at=None
        )
        
        epoch_repo.insert_epoch(epoch)
        
        return epoch

    def _run_daily_test(self, epoch: BenchmarkEpoch, test_date: date, miner: Miner):
        from packages.jobs.tasks.benchmark_test_execution_task import benchmark_test_execution_task
        
        networks = ['torus', 'bittensor']
        window_configs = [
            {'network': 'torus', 'window_days': 30},
            {'network': 'torus', 'window_days': 90},
            {'network': 'bittensor', 'window_days': 30},
            {'network': 'bittensor', 'window_days': 90},
        ]
        
        for config in window_configs:
            benchmark_test_execution_task.delay(
                epoch_id=str(epoch.epoch_id),
                hotkey=miner.hotkey,
                image_type=miner.image_type.value,
                test_date=str(test_date),
                network=config['network'],
                window_days=config['window_days'],
                processing_date=str(test_date)
            )

    def _is_epoch_complete(self, epoch: BenchmarkEpoch, current_date: date) -> bool:
        return current_date >= epoch.end_date

    def _finalize_epoch(self, epoch: BenchmarkEpoch, miner: Miner):
        from packages.jobs.tasks.benchmark_scoring_task import benchmark_scoring_task
        from packages.jobs.tasks.benchmark_cleanup_task import benchmark_cleanup_task
        
        benchmark_scoring_task.delay(
            epoch_id=str(epoch.epoch_id),
            hotkey=miner.hotkey,
            image_type=miner.image_type.value
        )
        
        benchmark_cleanup_task.delay(
            epoch_id=str(epoch.epoch_id),
            hotkey=miner.hotkey,
            image_type=miner.image_type.value
        )


@celery_app.task(
    bind=True,
    base=BenchmarkOrchestratorTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 3,
        'countdown': 300
    },
    time_limit=7200,
    soft_time_limit=7000
)
def benchmark_orchestrator_task(
    self,
    image_type: str,
    test_date: str,
):
    context = {
        'image_type': image_type,
        'test_date': test_date
    }
    
    return self.run(context)