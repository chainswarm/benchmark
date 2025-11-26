import os
from datetime import datetime
from statistics import mean
from typing import List
from uuid import UUID

from clickhouse_connect import get_client
from clickhouse_connect.driver import Client
from loguru import logger

from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import (
    AnalyticsDailyRun,
    BenchmarkScore,
    MLDailyRun,
    RunStatus,
)


class ScoringManager:
    PATTERN_ACCURACY_WEIGHT = 0.50
    DATA_CORRECTNESS_WEIGHT = 0.30
    PERFORMANCE_WEIGHT = 0.20

    def __init__(self):
        self.max_execution_time = int(os.environ.get('BENCHMARK_MAX_EXECUTION_TIME', 3600))
        self.validator_host = os.environ['VALIDATOR_CH_HOST']
        self.validator_port = int(os.environ['VALIDATOR_CH_PORT'])

    def calculate_analytics_epoch_score(
        self,
        epoch_id: UUID,
        hotkey: str,
        runs: List[AnalyticsDailyRun],
        baseline_avg_time: float
    ) -> BenchmarkScore:
        data_correctness_all_days = all(run.data_correctness_passed for run in runs)
        all_within_time_limit = all(
            run.execution_time_seconds <= self.max_execution_time for run in runs
        )
        
        if not data_correctness_all_days:
            logger.warning("Data correctness failed, score is 0", extra={
                "epoch_id": str(epoch_id),
                "hotkey": hotkey
            })
            return self._create_zero_score(epoch_id, hotkey, ImageType.ANALYTICS, runs)
        
        if not all_within_time_limit:
            logger.warning("Time limit exceeded, score is 0", extra={
                "epoch_id": str(epoch_id),
                "hotkey": hotkey
            })
            return self._create_zero_score(epoch_id, hotkey, ImageType.ANALYTICS, runs)
        
        pattern_accuracy_score = mean([run.synthetic_patterns_recall for run in runs])
        
        novelty_scores = []
        for run in runs:
            if run.novelty_patterns_reported > 0:
                novelty_scores.append(
                    run.novelty_patterns_validated / run.novelty_patterns_reported
                )
            else:
                novelty_scores.append(1.0)
        
        data_correctness_score = mean(novelty_scores)
        
        avg_execution_time = mean([run.execution_time_seconds for run in runs])
        performance_ratio = baseline_avg_time / avg_execution_time if avg_execution_time > 0 else 0.0
        performance_score = min(performance_ratio, 1.0)
        
        final_score = (
            self.PATTERN_ACCURACY_WEIGHT * pattern_accuracy_score +
            self.DATA_CORRECTNESS_WEIGHT * data_correctness_score +
            self.PERFORMANCE_WEIGHT * performance_score
        )
        
        logger.info("Calculated analytics epoch score", extra={
            "epoch_id": str(epoch_id),
            "hotkey": hotkey,
            "pattern_accuracy": pattern_accuracy_score,
            "data_correctness": data_correctness_score,
            "performance": performance_score,
            "final_score": final_score
        })
        
        return BenchmarkScore(
            epoch_id=epoch_id,
            hotkey=hotkey,
            image_type=ImageType.ANALYTICS,
            data_correctness_all_days=True,
            pattern_accuracy_score=pattern_accuracy_score,
            data_correctness_score=data_correctness_score,
            performance_score=performance_score,
            final_score=final_score,
            rank=0,
            baseline_comparison_ratio=performance_ratio,
            all_runs_within_time_limit=True,
            average_execution_time_seconds=avg_execution_time,
            calculated_at=datetime.now()
        )

    def calculate_ml_epoch_score(
        self,
        epoch_id: UUID,
        hotkey: str,
        runs: List[MLDailyRun],
        baseline_avg_time: float
    ) -> BenchmarkScore:
        data_correctness_all_days = all(run.data_correctness_passed for run in runs)
        all_within_time_limit = all(
            run.execution_time_seconds <= self.max_execution_time for run in runs
        )
        
        if not data_correctness_all_days:
            logger.warning("Data correctness failed, score is 0", extra={
                "epoch_id": str(epoch_id),
                "hotkey": hotkey
            })
            return self._create_zero_score(epoch_id, hotkey, ImageType.ML, runs)
        
        if not all_within_time_limit:
            logger.warning("Time limit exceeded, score is 0", extra={
                "epoch_id": str(epoch_id),
                "hotkey": hotkey
            })
            return self._create_zero_score(epoch_id, hotkey, ImageType.ML, runs)
        
        pattern_accuracy_score = mean([run.auc_roc for run in runs])
        
        data_correctness_score = 1.0
        
        avg_execution_time = mean([run.execution_time_seconds for run in runs])
        performance_ratio = baseline_avg_time / avg_execution_time if avg_execution_time > 0 else 0.0
        performance_score = min(performance_ratio, 1.0)
        
        final_score = (
            self.PATTERN_ACCURACY_WEIGHT * pattern_accuracy_score +
            self.DATA_CORRECTNESS_WEIGHT * data_correctness_score +
            self.PERFORMANCE_WEIGHT * performance_score
        )
        
        logger.info("Calculated ML epoch score", extra={
            "epoch_id": str(epoch_id),
            "hotkey": hotkey,
            "auc_roc": pattern_accuracy_score,
            "performance": performance_score,
            "final_score": final_score
        })
        
        return BenchmarkScore(
            epoch_id=epoch_id,
            hotkey=hotkey,
            image_type=ImageType.ML,
            data_correctness_all_days=True,
            pattern_accuracy_score=pattern_accuracy_score,
            data_correctness_score=data_correctness_score,
            performance_score=performance_score,
            final_score=final_score,
            rank=0,
            baseline_comparison_ratio=performance_ratio,
            all_runs_within_time_limit=True,
            average_execution_time_seconds=avg_execution_time,
            calculated_at=datetime.now()
        )

    def calculate_rankings(self, scores: List[BenchmarkScore]) -> List[BenchmarkScore]:
        sorted_scores = sorted(scores, key=lambda s: s.final_score, reverse=True)
        
        for rank, score in enumerate(sorted_scores, start=1):
            score.rank = rank
        
        logger.info("Calculated rankings", extra={
            "total_miners": len(sorted_scores),
            "top_score": sorted_scores[0].final_score if sorted_scores else 0
        })
        
        return sorted_scores

    def get_baseline_average_time(self, image_type: ImageType, network: str) -> float:
        client = self._get_validator_client()
        
        if image_type == ImageType.ANALYTICS:
            table = 'benchmark_analytics_baseline_runs'
        else:
            table = 'benchmark_ml_baseline_runs'
        
        query = f"""
        SELECT avg(execution_time_seconds)
        FROM {table}
        WHERE network = %(network)s
        ORDER BY test_date DESC
        LIMIT 7
        """
        
        result = client.query(query, parameters={'network': network})
        
        if result.result_rows and result.result_rows[0][0]:
            return float(result.result_rows[0][0])
        
        return self.max_execution_time

    def _get_validator_client(self) -> Client:
        return get_client(
            host=self.validator_host,
            port=self.validator_port,
            database='default'
        )

    def _create_zero_score(
        self,
        epoch_id: UUID,
        hotkey: str,
        image_type: ImageType,
        runs: list
    ) -> BenchmarkScore:
        avg_execution_time = mean([r.execution_time_seconds for r in runs]) if runs else 0.0
        all_within_time_limit = all(
            r.execution_time_seconds <= self.max_execution_time for r in runs
        )
        
        return BenchmarkScore(
            epoch_id=epoch_id,
            hotkey=hotkey,
            image_type=image_type,
            data_correctness_all_days=False,
            pattern_accuracy_score=0.0,
            data_correctness_score=0.0,
            performance_score=0.0,
            final_score=0.0,
            rank=0,
            baseline_comparison_ratio=0.0,
            all_runs_within_time_limit=all_within_time_limit,
            average_execution_time_seconds=avg_execution_time,
            calculated_at=datetime.now()
        )