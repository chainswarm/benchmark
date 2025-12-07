import os
from datetime import date, datetime, timedelta
from statistics import mean
from typing import List, Optional
from uuid import UUID, uuid4

from loguru import logger

from packages.benchmark.models.baseline import Baseline
from packages.benchmark.models.epoch import BenchmarkEpoch, EpochStatus
from packages.benchmark.models.miner import ImageType, Miner
from packages.benchmark.models.results import AnalyticsDailyRun, RunStatus
from packages.benchmark.models.tournament import (
    ParticipantStatus,
    ParticipantType,
    Tournament,
    TournamentParticipant,
    TournamentResult,
    TournamentStatus,
)


class TournamentManager:
    """Manages tournament lifecycle - creation, participant management, scoring."""
    
    PATTERN_ACCURACY_WEIGHT = 0.50
    DATA_CORRECTNESS_WEIGHT = 0.30
    PERFORMANCE_WEIGHT = 0.20
    
    def __init__(self):
        self.max_participants = int(os.environ.get('TOURNAMENT_MAX_PARTICIPANTS', 10))
        self.epoch_days = int(os.environ.get('TOURNAMENT_EPOCH_DAYS', 7))
        self.max_execution_time = int(os.environ.get('BENCHMARK_MAX_EXECUTION_TIME', 3600))
        self.test_networks = os.environ.get('TOURNAMENT_TEST_NETWORKS', 'torus,bittensor').split(',')
        self.test_window_days = [int(x) for x in os.environ.get('TOURNAMENT_TEST_WINDOWS', '30,90').split(',')]
    
    def create_tournament(
        self,
        name: str,
        image_type: ImageType,
        baseline: Baseline,
        registration_start: date,
        registration_end: date
    ) -> Tournament:
        """Create a new tournament with the current active baseline."""
        competition_start = registration_end + timedelta(days=1)
        competition_end = competition_start + timedelta(days=self.epoch_days - 1)
        
        tournament = Tournament(
            tournament_id=uuid4(),
            name=name,
            image_type=image_type,
            registration_start=registration_start,
            registration_end=registration_end,
            competition_start=competition_start,
            competition_end=competition_end,
            max_participants=self.max_participants,
            epoch_days=self.epoch_days,
            test_networks=self.test_networks,
            test_window_days=self.test_window_days,
            baseline_id=baseline.baseline_id,
            status=TournamentStatus.DRAFT,
            current_day=0,
            created_at=datetime.now(),
            winner_hotkey=None,
            baseline_beaten=False,
            completed_at=None
        )
        
        logger.info("Created tournament", extra={
            "tournament_id": str(tournament.tournament_id),
            "name": name,
            "image_type": image_type.value,
            "competition_start": str(competition_start),
            "competition_end": str(competition_end)
        })
        
        return tournament
    
    def create_baseline_participant(
        self,
        tournament: Tournament,
        baseline: Baseline
    ) -> TournamentParticipant:
        """Create the baseline as a participant (always order=0)."""
        hotkey = f"baseline_{baseline.version}"
        
        participant = TournamentParticipant(
            tournament_id=tournament.tournament_id,
            hotkey=hotkey,
            participant_type=ParticipantType.BASELINE,
            registered_at=datetime.now(),
            registration_order=0,  # Baseline always first
            github_repository=baseline.github_repository,
            docker_image_tag=baseline.docker_image_tag,
            miner_database_name=f"baseline_{baseline.image_type.value}",
            status=ParticipantStatus.REGISTERED,
            updated_at=datetime.now(),
            baseline_id=baseline.baseline_id
        )
        
        logger.info("Created baseline participant", extra={
            "tournament_id": str(tournament.tournament_id),
            "baseline_version": baseline.version
        })
        
        return participant
    
    def create_miner_participant(
        self,
        tournament: Tournament,
        miner: Miner,
        registration_order: int,
        docker_image_tag: str,
        miner_database_name: str
    ) -> TournamentParticipant:
        """Create a miner participant entry."""
        participant = TournamentParticipant(
            tournament_id=tournament.tournament_id,
            hotkey=miner.hotkey,
            participant_type=ParticipantType.MINER,
            registered_at=datetime.now(),
            registration_order=registration_order,
            github_repository=miner.github_repository,
            docker_image_tag=docker_image_tag,
            miner_database_name=miner_database_name,
            status=ParticipantStatus.REGISTERED,
            updated_at=datetime.now(),
            baseline_id=None
        )
        
        logger.info("Created miner participant", extra={
            "tournament_id": str(tournament.tournament_id),
            "hotkey": miner.hotkey,
            "order": registration_order
        })
        
        return participant
    
    def create_tournament_epoch(self, tournament: Tournament) -> BenchmarkEpoch:
        epoch = BenchmarkEpoch(
            epoch_id=uuid4(),
            hotkey=f"tournament_{tournament.tournament_id}",
            image_type=tournament.image_type,
            start_date=tournament.competition_start,
            end_date=tournament.competition_end,
            status=EpochStatus.PENDING,
            docker_image_tag="",
            miner_database_name="",
            created_at=datetime.now(),
            completed_at=None,
            tournament_id=tournament.tournament_id
        )
        
        logger.info("Created tournament epoch", extra={
            "epoch_id": str(epoch.epoch_id),
            "tournament_id": str(tournament.tournament_id),
            "start": str(epoch.start_date),
            "end": str(epoch.end_date)
        })
        
        return epoch
    
    def get_execution_queue(
        self,
        participants: List[TournamentParticipant]
    ) -> List[TournamentParticipant]:
        """Get ordered list of participants for daily execution."""
        return sorted(participants, key=lambda p: p.registration_order)
    
    def calculate_participant_score(
        self,
        tournament_id: UUID,
        participant: TournamentParticipant,
        runs: List[AnalyticsDailyRun],
        baseline_avg_time: float
    ) -> TournamentResult:
        data_correctness_all_days = all(run.data_correctness_passed for run in runs)
        all_within_time_limit = all(
            run.execution_time_seconds <= self.max_execution_time for run in runs
        )
        
        # Disqualification checks
        if not data_correctness_all_days or not all_within_time_limit:
            logger.warning("Participant disqualified", extra={
                "tournament_id": str(tournament_id),
                "hotkey": participant.hotkey,
                "data_correctness": data_correctness_all_days,
                "within_time": all_within_time_limit
            })
            return self._create_zero_result(tournament_id, participant, runs)
        
        pattern_accuracy_score = mean([run.synthetic_patterns_recall for run in runs])
        data_correctness_score = 1.0  # All passed
        
        avg_execution_time = mean([run.execution_time_seconds for run in runs])
        performance_ratio = baseline_avg_time / avg_execution_time if avg_execution_time > 0 else 0.0
        performance_score = min(performance_ratio, 1.0)
        
        final_score = (
            self.PATTERN_ACCURACY_WEIGHT * pattern_accuracy_score +
            self.DATA_CORRECTNESS_WEIGHT * data_correctness_score +
            self.PERFORMANCE_WEIGHT * performance_score
        )
        
        # Count unique days
        unique_days = len(set(run.test_date for run in runs))
        
        result = TournamentResult(
            tournament_id=tournament_id,
            hotkey=participant.hotkey,
            participant_type=participant.participant_type,
            pattern_accuracy_score=pattern_accuracy_score,
            data_correctness_score=data_correctness_score,
            performance_score=performance_score,
            final_score=final_score,
            data_correctness_all_days=True,
            all_runs_within_time_limit=True,
            days_completed=unique_days,
            total_runs_completed=len(runs),
            average_execution_time_seconds=avg_execution_time,
            baseline_comparison_ratio=performance_ratio,
            rank=0,  # Set later
            is_winner=False,
            beat_baseline=False,
            miners_beaten=0,
            calculated_at=datetime.now()
        )
        
        logger.info("Calculated participant score", extra={
            "tournament_id": str(tournament_id),
            "hotkey": participant.hotkey,
            "final_score": final_score
        })
        
        return result
    
    def determine_rankings(
        self,
        results: List[TournamentResult]
    ) -> List[TournamentResult]:
        """Sort results and assign rankings, determine winner."""
        sorted_results = sorted(results, key=lambda r: r.final_score, reverse=True)
        
        # Find baseline score
        baseline_score = 0.0
        for result in sorted_results:
            if result.participant_type == ParticipantType.BASELINE:
                baseline_score = result.final_score
                break
        
        # Assign rankings and determine who beat baseline
        for rank, result in enumerate(sorted_results, start=1):
            result.rank = rank
            result.is_winner = (rank == 1)
            result.beat_baseline = (result.final_score > baseline_score)
            
            # Count how many other participants this one beat
            miners_beaten = sum(1 for r in sorted_results if r.final_score < result.final_score)
            result.miners_beaten = miners_beaten
        
        winner = sorted_results[0] if sorted_results else None
        logger.info("Determined tournament rankings", extra={
            "total_participants": len(sorted_results),
            "winner": winner.hotkey if winner else None,
            "winner_score": winner.final_score if winner else 0,
            "baseline_score": baseline_score
        })
        
        return sorted_results
    
    def _create_zero_result(
        self,
        tournament_id: UUID,
        participant: TournamentParticipant,
        runs: List[AnalyticsDailyRun]
    ) -> TournamentResult:
        avg_time = mean([r.execution_time_seconds for r in runs]) if runs else 0.0
        unique_days = len(set(r.test_date for r in runs)) if runs else 0
        
        return TournamentResult(
            tournament_id=tournament_id,
            hotkey=participant.hotkey,
            participant_type=participant.participant_type,
            pattern_accuracy_score=0.0,
            data_correctness_score=0.0,
            performance_score=0.0,
            final_score=0.0,
            data_correctness_all_days=False,
            all_runs_within_time_limit=False,
            days_completed=unique_days,
            total_runs_completed=len(runs),
            average_execution_time_seconds=avg_time,
            baseline_comparison_ratio=0.0,
            rank=0,
            is_winner=False,
            beat_baseline=False,
            miners_beaten=0,
            calculated_at=datetime.now()
        )