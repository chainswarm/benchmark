import os
from datetime import date, datetime
from typing import List, Union
from uuid import UUID, uuid4

from clickhouse_connect import get_client
from clickhouse_connect.driver import Client

from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import (
    AnalyticsDailyRun,
    BenchmarkScore,
    MLDailyRun,
    RunStatus,
)
from packages.storage.repositories.base_repository import BaseRepository
from packages.utils.decorators import log_errors


class BenchmarkResultsRepository(BaseRepository):
    
    def __init__(self, client: Client = None):
        if client is None:
            client = get_client(
                host=os.environ['VALIDATOR_CH_HOST'],
                port=int(os.environ['VALIDATOR_CH_PORT']),
                database='default'
            )
        super().__init__(client)

    @log_errors
    def create_run(
        self,
        epoch_id: UUID,
        hotkey: str,
        image_type: ImageType,
        test_date: date,
        network: str,
        window_days: int,
        processing_date: date
    ) -> UUID:
        run_id = uuid4()
        now = datetime.now()
        
        if image_type == ImageType.ANALYTICS:
            table = 'benchmark_analytics_daily_runs'
            query = f"""
            INSERT INTO {table} 
            (run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
             execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
             synthetic_patterns_expected, synthetic_patterns_found, synthetic_patterns_recall,
             novelty_patterns_reported, novelty_patterns_validated,
             novelty_addresses_valid, novelty_connections_valid,
             all_addresses_exist, all_connections_exist, data_correctness_passed,
             status, error_message, created_at)
            VALUES (%(run_id)s, %(epoch_id)s, %(hotkey)s, %(test_date)s, %(network)s, %(window_days)s, %(processing_date)s,
                    0, 0, 0, 0, 0, 0, 0, 0, true, true, true, true, true,
                    'pending', NULL, %(created_at)s)
            """
        else:
            table = 'benchmark_ml_daily_runs'
            query = f"""
            INSERT INTO {table} 
            (run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
             execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
             auc_roc, precision_at_recall_80, all_addresses_exist, data_correctness_passed,
             status, error_message, created_at)
            VALUES (%(run_id)s, %(epoch_id)s, %(hotkey)s, %(test_date)s, %(network)s, %(window_days)s, %(processing_date)s,
                    0, 0, 0, 0, 0, true, true, 'pending', NULL, %(created_at)s)
            """
        
        self.client.command(query, parameters={
            'run_id': str(run_id),
            'epoch_id': str(epoch_id),
            'hotkey': hotkey,
            'test_date': test_date,
            'network': network,
            'window_days': window_days,
            'processing_date': processing_date,
            'created_at': now
        })
        
        return run_id

    @log_errors
    def update_run_status(
        self,
        run_id: UUID,
        image_type: ImageType,
        status: RunStatus,
        error_message: str = None
    ) -> None:
        if image_type == ImageType.ANALYTICS:
            table = 'benchmark_analytics_daily_runs'
        else:
            table = 'benchmark_ml_daily_runs'
        
        query = f"""
        ALTER TABLE {table}
        UPDATE status = %(status)s, error_message = %(error_message)s
        WHERE run_id = %(run_id)s
        """
        
        self.client.command(query, parameters={
            'run_id': str(run_id),
            'status': status.value,
            'error_message': error_message
        })

    @log_errors
    def update_run_execution_metrics(
        self,
        run_id: UUID,
        image_type: ImageType,
        execution_time: float,
        exit_code: int,
        gpu_memory_peak: float
    ) -> None:
        if image_type == ImageType.ANALYTICS:
            table = 'benchmark_analytics_daily_runs'
        else:
            table = 'benchmark_ml_daily_runs'
        
        query = f"""
        ALTER TABLE {table}
        UPDATE execution_time_seconds = %(execution_time)s,
               container_exit_code = %(exit_code)s,
               gpu_memory_peak_mb = %(gpu_memory_peak)s
        WHERE run_id = %(run_id)s
        """
        
        self.client.command(query, parameters={
            'run_id': str(run_id),
            'execution_time': execution_time,
            'exit_code': exit_code,
            'gpu_memory_peak': gpu_memory_peak
        })

    @log_errors
    def update_analytics_run_validation(
        self,
        run_id: UUID,
        synthetic_patterns_expected: int,
        synthetic_patterns_found: int,
        synthetic_patterns_recall: float,
        novelty_patterns_reported: int,
        novelty_patterns_validated: int,
        novelty_addresses_valid: bool,
        novelty_connections_valid: bool,
        all_addresses_exist: bool,
        all_connections_exist: bool,
        data_correctness_passed: bool
    ) -> None:
        query = """
        ALTER TABLE benchmark_analytics_daily_runs
        UPDATE synthetic_patterns_expected = %(synthetic_patterns_expected)s,
               synthetic_patterns_found = %(synthetic_patterns_found)s,
               synthetic_patterns_recall = %(synthetic_patterns_recall)s,
               novelty_patterns_reported = %(novelty_patterns_reported)s,
               novelty_patterns_validated = %(novelty_patterns_validated)s,
               novelty_addresses_valid = %(novelty_addresses_valid)s,
               novelty_connections_valid = %(novelty_connections_valid)s,
               all_addresses_exist = %(all_addresses_exist)s,
               all_connections_exist = %(all_connections_exist)s,
               data_correctness_passed = %(data_correctness_passed)s
        WHERE run_id = %(run_id)s
        """
        
        self.client.command(query, parameters={
            'run_id': str(run_id),
            'synthetic_patterns_expected': synthetic_patterns_expected,
            'synthetic_patterns_found': synthetic_patterns_found,
            'synthetic_patterns_recall': synthetic_patterns_recall,
            'novelty_patterns_reported': novelty_patterns_reported,
            'novelty_patterns_validated': novelty_patterns_validated,
            'novelty_addresses_valid': novelty_addresses_valid,
            'novelty_connections_valid': novelty_connections_valid,
            'all_addresses_exist': all_addresses_exist,
            'all_connections_exist': all_connections_exist,
            'data_correctness_passed': data_correctness_passed
        })

    @log_errors
    def update_ml_run_validation(
        self,
        run_id: UUID,
        auc_roc: float,
        precision_at_recall_80: float,
        all_addresses_exist: bool,
        data_correctness_passed: bool
    ) -> None:
        query = """
        ALTER TABLE benchmark_ml_daily_runs
        UPDATE auc_roc = %(auc_roc)s,
               precision_at_recall_80 = %(precision_at_recall_80)s,
               all_addresses_exist = %(all_addresses_exist)s,
               data_correctness_passed = %(data_correctness_passed)s
        WHERE run_id = %(run_id)s
        """
        
        self.client.command(query, parameters={
            'run_id': str(run_id),
            'auc_roc': auc_roc,
            'precision_at_recall_80': precision_at_recall_80,
            'all_addresses_exist': all_addresses_exist,
            'data_correctness_passed': data_correctness_passed
        })

    @log_errors
    def get_runs_for_epoch(
        self,
        epoch_id: UUID,
        image_type: ImageType
    ) -> List[Union[AnalyticsDailyRun, MLDailyRun]]:
        if image_type == ImageType.ANALYTICS:
            return self._get_analytics_runs_for_epoch(epoch_id)
        else:
            return self._get_ml_runs_for_epoch(epoch_id)

    def _get_analytics_runs_for_epoch(self, epoch_id: UUID) -> List[AnalyticsDailyRun]:
        query = """
        SELECT run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
               execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
               synthetic_patterns_expected, synthetic_patterns_found, synthetic_patterns_recall,
               novelty_patterns_reported, novelty_patterns_validated,
               novelty_addresses_valid, novelty_connections_valid,
               all_addresses_exist, all_connections_exist, data_correctness_passed,
               status, error_message, created_at
        FROM benchmark_analytics_daily_runs
        WHERE epoch_id = %(epoch_id)s
        ORDER BY test_date, network
        """
        
        result = self.client.query(query, parameters={'epoch_id': str(epoch_id)})
        
        runs = []
        for row in result.result_rows:
            runs.append(AnalyticsDailyRun(
                run_id=UUID(row[0]) if isinstance(row[0], str) else row[0],
                epoch_id=UUID(row[1]) if isinstance(row[1], str) else row[1],
                hotkey=row[2],
                test_date=row[3],
                network=row[4],
                window_days=row[5],
                processing_date=row[6],
                execution_time_seconds=row[7],
                container_exit_code=row[8],
                gpu_memory_peak_mb=row[9],
                synthetic_patterns_expected=row[10],
                synthetic_patterns_found=row[11],
                synthetic_patterns_recall=row[12],
                novelty_patterns_reported=row[13],
                novelty_patterns_validated=row[14],
                novelty_addresses_valid=row[15],
                novelty_connections_valid=row[16],
                all_addresses_exist=row[17],
                all_connections_exist=row[18],
                data_correctness_passed=row[19],
                status=RunStatus(row[20]),
                error_message=row[21],
                created_at=row[22]
            ))
        
        return runs

    def _get_ml_runs_for_epoch(self, epoch_id: UUID) -> List[MLDailyRun]:
        query = """
        SELECT run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
               execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
               auc_roc, precision_at_recall_80, all_addresses_exist, data_correctness_passed,
               status, error_message, created_at
        FROM benchmark_ml_daily_runs
        WHERE epoch_id = %(epoch_id)s
        ORDER BY test_date, network
        """
        
        result = self.client.query(query, parameters={'epoch_id': str(epoch_id)})
        
        runs = []
        for row in result.result_rows:
            runs.append(MLDailyRun(
                run_id=UUID(row[0]) if isinstance(row[0], str) else row[0],
                epoch_id=UUID(row[1]) if isinstance(row[1], str) else row[1],
                hotkey=row[2],
                test_date=row[3],
                network=row[4],
                window_days=row[5],
                processing_date=row[6],
                execution_time_seconds=row[7],
                container_exit_code=row[8],
                gpu_memory_peak_mb=row[9],
                auc_roc=row[10],
                precision_at_recall_80=row[11],
                all_addresses_exist=row[12],
                data_correctness_passed=row[13],
                status=RunStatus(row[14]),
                error_message=row[15],
                created_at=row[16]
            ))
        
        return runs

    @log_errors
    def insert_score(self, score: BenchmarkScore) -> None:
        query = """
        INSERT INTO benchmark_scores
        (epoch_id, hotkey, image_type, data_correctness_all_days,
         pattern_accuracy_score, data_correctness_score, performance_score,
         final_score, rank, baseline_comparison_ratio,
         all_runs_within_time_limit, average_execution_time_seconds, calculated_at)
        VALUES (%(epoch_id)s, %(hotkey)s, %(image_type)s, %(data_correctness_all_days)s,
                %(pattern_accuracy_score)s, %(data_correctness_score)s, %(performance_score)s,
                %(final_score)s, %(rank)s, %(baseline_comparison_ratio)s,
                %(all_runs_within_time_limit)s, %(average_execution_time_seconds)s, %(calculated_at)s)
        """
        
        self.client.command(query, parameters={
            'epoch_id': str(score.epoch_id),
            'hotkey': score.hotkey,
            'image_type': score.image_type.value,
            'data_correctness_all_days': score.data_correctness_all_days,
            'pattern_accuracy_score': score.pattern_accuracy_score,
            'data_correctness_score': score.data_correctness_score,
            'performance_score': score.performance_score,
            'final_score': score.final_score,
            'rank': score.rank,
            'baseline_comparison_ratio': score.baseline_comparison_ratio,
            'all_runs_within_time_limit': score.all_runs_within_time_limit,
            'average_execution_time_seconds': score.average_execution_time_seconds,
            'calculated_at': score.calculated_at
        })

    @log_errors
    def get_all_latest_scores(self, image_type: ImageType) -> List[BenchmarkScore]:
        query = """
        SELECT epoch_id, hotkey, image_type, data_correctness_all_days,
               pattern_accuracy_score, data_correctness_score, performance_score,
               final_score, rank, baseline_comparison_ratio,
               all_runs_within_time_limit, average_execution_time_seconds, calculated_at
        FROM benchmark_scores
        WHERE image_type = %(image_type)s
        ORDER BY hotkey, calculated_at DESC
        """
        
        result = self.client.query(query, parameters={'image_type': image_type.value})
        
        scores = []
        seen_hotkeys = set()
        
        for row in result.result_rows:
            hotkey = row[1]
            if hotkey not in seen_hotkeys:
                seen_hotkeys.add(hotkey)
                scores.append(BenchmarkScore(
                    epoch_id=UUID(row[0]) if isinstance(row[0], str) else row[0],
                    hotkey=row[1],
                    image_type=ImageType(row[2]),
                    data_correctness_all_days=row[3],
                    pattern_accuracy_score=row[4],
                    data_correctness_score=row[5],
                    performance_score=row[6],
                    final_score=row[7],
                    rank=row[8],
                    baseline_comparison_ratio=row[9],
                    all_runs_within_time_limit=row[10],
                    average_execution_time_seconds=row[11],
                    calculated_at=row[12]
                ))
        
        return scores

    @log_errors
    def update_score_rank(
        self,
        epoch_id: UUID,
        hotkey: str,
        image_type: ImageType,
        rank: int
    ) -> None:
        query = """
        ALTER TABLE benchmark_scores
        UPDATE rank = %(rank)s
        WHERE epoch_id = %(epoch_id)s AND hotkey = %(hotkey)s AND image_type = %(image_type)s
        """
        
        self.client.command(query, parameters={
            'epoch_id': str(epoch_id),
            'hotkey': hotkey,
            'image_type': image_type.value,
            'rank': rank
        })