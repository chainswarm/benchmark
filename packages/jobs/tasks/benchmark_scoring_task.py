from datetime import datetime
from typing import List
from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.scoring_manager import ScoringManager
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import AnalyticsDailyRun, BenchmarkScore, MLDailyRun
from packages.jobs.celery_app import celery_app


class BenchmarkScoringTask(BaseTask, Singleton):

    def execute_task(self, context: dict):
        epoch_id = UUID(context['epoch_id'])
        hotkey = context['hotkey']
        image_type = ImageType(context['image_type'])
        
        logger.info("Starting scoring calculation", extra={
            "epoch_id": str(epoch_id),
            "hotkey": hotkey,
            "image_type": image_type.value
        })
        
        from packages.storage.repositories.benchmark_results_repository import BenchmarkResultsRepository
        from packages.storage.repositories.benchmark_epoch_repository import BenchmarkEpochRepository
        
        results_repo = BenchmarkResultsRepository()
        epoch_repo = BenchmarkEpochRepository()
        scoring_manager = ScoringManager()
        
        runs = results_repo.get_runs_for_epoch(epoch_id, image_type)
        
        if not runs:
            logger.warning("No runs found for epoch", extra={
                "epoch_id": str(epoch_id)
            })
            return {
                "status": "no_runs",
                "epoch_id": str(epoch_id)
            }
        
        networks = set(run.network for run in runs)
        baseline_times = {}
        
        for network in networks:
            baseline_times[network] = scoring_manager.get_baseline_average_time(
                image_type=image_type,
                network=network
            )
        
        avg_baseline_time = sum(baseline_times.values()) / len(baseline_times)
        
        if image_type == ImageType.ANALYTICS:
            score = scoring_manager.calculate_analytics_epoch_score(
                epoch_id=epoch_id,
                hotkey=hotkey,
                runs=runs,
                baseline_avg_time=avg_baseline_time
            )
        else:
            score = scoring_manager.calculate_ml_epoch_score(
                epoch_id=epoch_id,
                hotkey=hotkey,
                runs=runs,
                baseline_avg_time=avg_baseline_time
            )
        
        results_repo.insert_score(score)
        
        epoch_repo.update_epoch_status(
            epoch_id=epoch_id,
            status='completed',
            completed_at=datetime.now()
        )
        
        self._update_rankings(results_repo, scoring_manager, image_type)
        
        logger.info("Scoring completed", extra={
            "epoch_id": str(epoch_id),
            "hotkey": hotkey,
            "final_score": score.final_score,
            "rank": score.rank
        })
        
        return {
            "status": "success",
            "epoch_id": str(epoch_id),
            "final_score": score.final_score
        }

    def _update_rankings(
        self,
        results_repo,
        scoring_manager: ScoringManager,
        image_type: ImageType
    ):
        all_scores = results_repo.get_all_latest_scores(image_type)
        
        ranked_scores = scoring_manager.calculate_rankings(all_scores)
        
        for score in ranked_scores:
            results_repo.update_score_rank(
                epoch_id=score.epoch_id,
                hotkey=score.hotkey,
                image_type=image_type,
                rank=score.rank
            )


@celery_app.task(
    bind=True,
    base=BenchmarkScoringTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=600,
    soft_time_limit=550
)
def benchmark_scoring_task(
    self,
    epoch_id: str,
    hotkey: str,
    image_type: str,
):
    context = {
        'epoch_id': epoch_id,
        'hotkey': hotkey,
        'image_type': image_type
    }
    
    return self.run(context)