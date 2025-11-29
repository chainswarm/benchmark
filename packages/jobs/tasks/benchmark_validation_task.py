from datetime import date
from uuid import UUID

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.managers.dataset_manager import DatasetManager
from packages.benchmark.managers.validation_manager import ValidationManager
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import RunStatus
from packages.jobs.celery_app import celery_app


class BenchmarkValidationTask(BaseTask, Singleton):

    def execute_task(self, context: dict):
        run_id = UUID(context['run_id'])
        epoch_id = UUID(context['epoch_id'])
        hotkey = context['hotkey']
        image_type = ImageType(context['image_type'])
        network = context['network']
        window_days = context['window_days']
        processing_date = context['processing_date']
        miner_database = context['miner_database']
        
        logger.info("Starting validation", extra={
            "run_id": str(run_id),
            "hotkey": hotkey,
            "network": network
        })
        
        from packages.storage.repositories.benchmark_results_repository import BenchmarkResultsRepository
        
        results_repo = BenchmarkResultsRepository()
        dataset_manager = DatasetManager()
        validation_manager = ValidationManager()
        
        ground_truth = dataset_manager.get_ground_truth(network, processing_date, window_days)
        
        miner_patterns = self._get_miner_patterns(miner_database, image_type)
        
        if image_type == ImageType.ANALYTICS:
            recall_metrics = validation_manager.compare_synthetic_patterns(
                miner_patterns=miner_patterns,
                ground_truth=ground_truth
            )
            
            novelty_patterns = self._get_novelty_patterns(miner_patterns, ground_truth)
            
            novelty_result = validation_manager.validate_novelty_patterns(
                patterns=novelty_patterns,
                network=network
            )
            
            data_correctness_passed = (
                novelty_result.addresses_valid and
                novelty_result.connections_valid
            )
            
            results_repo.update_analytics_run_validation(
                run_id=run_id,
                synthetic_patterns_expected=recall_metrics.patterns_expected,
                synthetic_patterns_found=recall_metrics.patterns_found,
                synthetic_patterns_recall=recall_metrics.recall,
                novelty_patterns_reported=novelty_result.patterns_reported,
                novelty_patterns_validated=novelty_result.patterns_validated,
                novelty_addresses_valid=novelty_result.addresses_valid,
                novelty_connections_valid=novelty_result.connections_valid,
                all_addresses_exist=novelty_result.addresses_valid,
                all_connections_exist=novelty_result.connections_valid,
                data_correctness_passed=data_correctness_passed
            )
            
        else:
            risk_scores = self._get_ml_risk_scores(miner_database)
            
            auc_roc, precision_at_recall_80 = self._calculate_ml_metrics(
                risk_scores=risk_scores,
                ground_truth=ground_truth
            )
            
            all_addresses_exist = validation_manager.validate_addresses_exist(
                addresses=list(risk_scores.keys()),
                network=network
            )
            
            data_correctness_passed = all_addresses_exist
            
            results_repo.update_ml_run_validation(
                run_id=run_id,
                auc_roc=auc_roc,
                precision_at_recall_80=precision_at_recall_80,
                all_addresses_exist=all_addresses_exist,
                data_correctness_passed=data_correctness_passed
            )
        
        results_repo.update_run_status(run_id, image_type, RunStatus.COMPLETED)
        
        logger.info("Validation completed", extra={
            "run_id": str(run_id),
            "data_correctness_passed": data_correctness_passed
        })
        
        return {
            "status": "success",
            "run_id": str(run_id),
            "data_correctness_passed": data_correctness_passed
        }

    def _get_miner_patterns(self, miner_database: str, image_type: ImageType) -> list:
        from clickhouse_connect import get_client
        import os
        
        client = get_client(
            host=os.environ['VALIDATOR_CH_HOST'],
            port=int(os.environ['VALIDATOR_CH_PORT']),
            database=miner_database
        )
        
        if image_type == ImageType.ANALYTICS:
            query = """
            SELECT pattern_id, pattern_type, addresses, transactions, confidence
            FROM miner_output_patterns
            """
            
            result = client.query(query)
            
            patterns = []
            for row in result.result_rows:
                patterns.append({
                    'pattern_id': row[0],
                    'pattern_type': row[1],
                    'addresses': row[2],
                    'transactions': row[3],
                    'confidence': row[4]
                })
            
            return patterns
        
        return []

    def _get_novelty_patterns(self, miner_patterns: list, ground_truth) -> list:
        ground_truth_pattern_ids = set(ground_truth['pattern_id'].unique())
        
        novelty_patterns = []
        for pattern in miner_patterns:
            if pattern['pattern_id'] not in ground_truth_pattern_ids:
                novelty_patterns.append(pattern)
        
        return novelty_patterns

    def _get_ml_risk_scores(self, miner_database: str) -> dict:
        from clickhouse_connect import get_client
        import os
        
        client = get_client(
            host=os.environ['VALIDATOR_CH_HOST'],
            port=int(os.environ['VALIDATOR_CH_PORT']),
            database=miner_database
        )
        
        query = """
        SELECT address, risk_score
        FROM miner_risk_scores
        """
        
        result = client.query(query)
        
        risk_scores = {}
        for row in result.result_rows:
            risk_scores[row[0]] = row[1]
        
        return risk_scores

    def _calculate_ml_metrics(self, risk_scores: dict, ground_truth) -> tuple:
        from sklearn.metrics import roc_auc_score, precision_recall_curve
        import numpy as np
        
        gt_addresses = set(ground_truth['address'].unique())
        
        y_true = []
        y_scores = []
        
        for address, score in risk_scores.items():
            y_scores.append(score)
            y_true.append(1 if address in gt_addresses else 0)
        
        if len(set(y_true)) < 2:
            return 0.5, 0.0
        
        auc_roc = roc_auc_score(y_true, y_scores)
        
        precision, recall, _ = precision_recall_curve(y_true, y_scores)
        
        precision_at_recall_80 = 0.0
        for p, r in zip(precision, recall):
            if r >= 0.80:
                precision_at_recall_80 = p
                break
        
        return auc_roc, precision_at_recall_80


@celery_app.task(
    bind=True,
    base=BenchmarkValidationTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=1800,
    soft_time_limit=1700
)
def benchmark_validation_task(
    self,
    run_id: str,
    epoch_id: str,
    hotkey: str,
    image_type: str,
    network: str,
    window_days: int,
    processing_date: str,
    miner_database: str,
):
    context = {
        'run_id': run_id,
        'epoch_id': epoch_id,
        'hotkey': hotkey,
        'image_type': image_type,
        'network': network,
        'window_days': window_days,
        'processing_date': processing_date,
        'miner_database': miner_database
    }
    
    return self.run(context)