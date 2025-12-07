from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from packages.api.models.tournament_responses import (
    TournamentsListResponse,
    TournamentListItem,
    TournamentWinnerSummary,
    PaginationInfo,
    TournamentDetailsResponse,
    TournamentSchedule,
    TournamentConfiguration,
    TournamentBaseline,
    TournamentParticipantsSummary,
    TournamentResultsSummary,
    LeaderboardResponse,
    LeaderboardEntry,
    ParticipantScores,
    ParticipantStats,
    TournamentDayResponse,
    DayDataset,
    ParticipantDayRun,
    NetworkRun,
    SyntheticPatterns,
    NoveltyPatterns,
    DataValidation,
    RunPerformance,
    BaselineComparison,
    DisqualificationInfo,
    ParticipantHistoryResponse,
    ParticipantRegistration,
    ParticipantStatusInfo,
    ParticipantResult,
    DailyPerformance,
    NetworkDayPerformance,
)
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.tournament import TournamentStatus
from packages.storage.repositories.tournament_repository import TournamentRepository
from packages.storage.repositories.baseline_repository import BaselineRepository


class TournamentService:
    
    def __init__(
        self,
        tournament_repository: TournamentRepository,
        baseline_repository: BaselineRepository
    ):
        self.tournament_repository = tournament_repository
        self.baseline_repository = baseline_repository
    
    def list_tournaments(
        self,
        image_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> TournamentsListResponse:
        img_type = ImageType(image_type) if image_type else None
        
        if status:
            tournaments = self.tournament_repository.get_tournaments_by_status(TournamentStatus(status))
        else:
            all_tournaments = []
            for s in TournamentStatus:
                all_tournaments.extend(self.tournament_repository.get_tournaments_by_status(s))
            tournaments = all_tournaments
        
        if img_type:
            tournaments = [t for t in tournaments if t.image_type == img_type]
        
        tournaments.sort(key=lambda t: t.competition_start, reverse=True)
        
        total = len(tournaments)
        paginated = tournaments[offset:offset + limit]
        
        items = []
        for t in paginated:
            participants = self.tournament_repository.get_participants(t.tournament_id)
            miner_count = len([p for p in participants if p.participant_type.value == 'miner'])
            
            winner = None
            if t.winner_hotkey:
                winner = TournamentWinnerSummary(
                    hotkey=t.winner_hotkey,
                    beat_baseline=t.baseline_beaten
                )
            
            items.append(TournamentListItem(
                tournament_id=t.tournament_id,
                name=t.name,
                image_type=t.image_type.value,
                status=t.status.value,
                competition_start=t.competition_start,
                competition_end=t.competition_end,
                participant_count=miner_count,
                winner=winner,
                created_at=t.created_at,
                completed_at=t.completed_at
            ))
        
        return TournamentsListResponse(
            tournaments=items,
            pagination=PaginationInfo(
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + limit) < total
            )
        )
    
    def get_tournament_details(self, tournament_id: UUID) -> TournamentDetailsResponse:
        tournament = self.tournament_repository.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        baseline = self.baseline_repository.get_baseline_by_id(tournament.baseline_id)
        baseline_info = TournamentBaseline(
            baseline_id=tournament.baseline_id,
            version=baseline.version if baseline else "unknown",
            hotkey="baseline-chainswarm",
            source_tournament_id=baseline.originated_from_tournament_id if baseline else None
        )
        
        participants = self.tournament_repository.get_participants(tournament_id)
        active_count = len([
            p for p in participants 
            if not p.is_disqualified and p.participant_type.value == 'miner'
        ])
        disqualified_count = len([p for p in participants if p.is_disqualified])
        total_miners = len([p for p in participants if p.participant_type.value == 'miner'])
        
        return TournamentDetailsResponse(
            tournament_id=tournament.tournament_id,
            name=tournament.name,
            image_type=tournament.image_type.value,
            status=tournament.status.value,
            schedule=TournamentSchedule(
                registration_start=tournament.registration_start,
                registration_end=tournament.registration_end,
                competition_start=tournament.competition_start,
                competition_end=tournament.competition_end
            ),
            configuration=TournamentConfiguration(
                max_participants=tournament.max_participants,
                epoch_days=tournament.epoch_days,
                test_networks=tournament.test_networks,
                test_window_days=tournament.test_window_days
            ),
            baseline=baseline_info,
            participants=TournamentParticipantsSummary(
                total=total_miners,
                active=active_count,
                disqualified=disqualified_count
            ),
            results=TournamentResultsSummary(
                winner_hotkey=tournament.winner_hotkey,
                baseline_beaten=tournament.baseline_beaten,
                current_day=tournament.current_day,
                days_completed=tournament.current_day  # Assuming current_day tracks completed days
            ),
            created_at=tournament.created_at,
            completed_at=tournament.completed_at
        )
    
    def get_leaderboard(self, tournament_id: UUID) -> LeaderboardResponse:
        tournament = self.tournament_repository.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        results = self.tournament_repository.get_results(tournament_id)
        participants = self.tournament_repository.get_participants(tournament_id)
        
        participant_map = {p.hotkey: p for p in participants}
        
        entries = []
        for r in results:
            p = participant_map.get(r.hotkey)
            
            entries.append(LeaderboardEntry(
                rank=r.rank,
                hotkey=r.hotkey,
                participant_type=r.participant_type.value,
                is_winner=r.is_winner,
                is_disqualified=p.is_disqualified if p else False,
                disqualification_reason=p.disqualification_reason if p else None,
                disqualified_on_day=p.disqualified_on_day if p else None,
                scores=ParticipantScores(
                    final_score=r.final_score,
                    pattern_accuracy_score=r.pattern_accuracy_score,
                    data_correctness_score=r.data_correctness_score,
                    performance_score=r.performance_score
                ),
                stats=ParticipantStats(
                    days_completed=r.days_completed,
                    total_runs_completed=r.total_runs_completed,
                    average_execution_time_seconds=r.average_execution_time_seconds,
                    baseline_comparison_ratio=r.baseline_comparison_ratio,
                    beat_baseline=r.beat_baseline,
                    miners_beaten=r.miners_beaten
                )
            ))
        
        return LeaderboardResponse(
            tournament_id=tournament_id,
            status=tournament.status.value,
            leaderboard=entries
        )
    
    def get_tournament_day(self, tournament_id: UUID, day_number: int) -> TournamentDayResponse:
        tournament = self.tournament_repository.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        test_date = tournament.competition_start + timedelta(days=day_number - 1)
        
        daily_runs = self.tournament_repository.get_daily_runs_for_tournament(tournament_id, test_date)
        
        if not daily_runs:
            raise ValueError(f"No runs found for tournament {tournament_id} day {day_number}")
        
        runs_by_hotkey = {}
        for run in daily_runs:
            if run.hotkey not in runs_by_hotkey:
                runs_by_hotkey[run.hotkey] = []
            runs_by_hotkey[run.hotkey].append(run)
        
        networks_tested = list(set(r.network for r in daily_runs))
        window_days_tested = list(set(r.window_days for r in daily_runs))
        
        baseline_runs = {
            (r.network, r.window_days): r 
            for r in daily_runs 
            if r.participant_type == 'baseline'
        }
        
        participant_runs = []
        for hotkey, runs in runs_by_hotkey.items():
            first_run = runs[0]
            
            network_runs = []
            for run in runs:
                baseline_comparison = None
                if run.participant_type == 'miner':
                    baseline_run = baseline_runs.get((run.network, run.window_days))
                    if baseline_run:
                        synthetic_ratio = (
                            run.synthetic_patterns_recall / baseline_run.synthetic_patterns_recall 
                            if baseline_run.synthetic_patterns_recall > 0 else 0
                        )
                        novelty_ratio = (
                            run.novelty_patterns_validated / baseline_run.novelty_patterns_validated 
                            if baseline_run.novelty_patterns_validated > 0 else 0
                        )
                        exec_ratio = (
                            run.execution_time_seconds / baseline_run.execution_time_seconds 
                            if baseline_run.execution_time_seconds > 0 else 0
                        )
                        baseline_comparison = BaselineComparison(
                            synthetic_recall_vs_baseline=synthetic_ratio,
                            novelty_vs_baseline=novelty_ratio,
                            execution_time_vs_baseline=exec_ratio
                        )
                
                disqualification = None
                if run.is_disqualified:
                    disqualification = DisqualificationInfo(
                        is_disqualified=True,
                        reason=run.disqualification_reason,
                        message=run.disqualification_reason
                    )
                
                network_runs.append(NetworkRun(
                    network=run.network,
                    window_days=run.window_days,
                    run_id=run.run_id,
                    synthetic_patterns=SyntheticPatterns(
                        expected=run.synthetic_patterns_expected,
                        found=run.synthetic_patterns_found,
                        recall=run.synthetic_patterns_recall
                    ),
                    novelty_patterns=NoveltyPatterns(
                        reported=run.novelty_patterns_reported,
                        validated=run.novelty_patterns_validated,
                        addresses_valid=run.novelty_addresses_valid,
                        connections_valid=run.novelty_connections_valid
                    ),
                    data_validation=DataValidation(
                        all_addresses_exist=run.all_addresses_exist,
                        all_connections_exist=run.all_connections_exist,
                        data_correctness_passed=run.data_correctness_passed
                    ),
                    performance=RunPerformance(
                        execution_time_seconds=run.execution_time_seconds,
                        container_exit_code=run.container_exit_code,
                        gpu_memory_peak_mb=run.gpu_memory_peak_mb
                    ),
                    baseline_comparison=baseline_comparison,
                    disqualification=disqualification,
                    status=run.status.value,
                    started_at=run.created_at,  # Assuming created_at is start time
                    completed_at=None
                ))
            
            status = "completed"
            if any(r.is_disqualified for r in runs):
                status = "disqualified"
            elif any(r.status.value == 'failed' for r in runs):
                status = "failed"
            
            participant_runs.append(ParticipantDayRun(
                run_order=first_run.run_order,
                participant_type=first_run.participant_type,
                hotkey=hotkey,
                status=status,
                network_runs=network_runs
            ))
        
        participant_runs.sort(key=lambda x: x.run_order)
        
        return TournamentDayResponse(
            tournament_id=tournament_id,
            day_number=day_number,
            test_date=test_date,
            dataset=DayDataset(
                networks_tested=networks_tested,
                window_days_tested=window_days_tested,
                total_runs=len(daily_runs)
            ),
            runs=participant_runs
        )
    
    def get_participant_history(self, tournament_id: UUID, hotkey: str) -> ParticipantHistoryResponse:
        tournament = self.tournament_repository.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        participant = self.tournament_repository.get_participant(tournament_id, hotkey)
        if not participant:
            raise ValueError(f"Participant {hotkey} not found in tournament {tournament_id}")
        
        result = self.tournament_repository.get_result(tournament_id, hotkey)
        
        runs = self.tournament_repository.get_participant_runs(tournament_id, hotkey)
        
        runs_by_date = {}
        for run in runs:
            if run.test_date not in runs_by_date:
                runs_by_date[run.test_date] = []
            runs_by_date[run.test_date].append(run)
        
        daily_performance = []
        for test_date, day_runs in sorted(runs_by_date.items()):
            day_number = (test_date - tournament.competition_start).days + 1
            
            networks = {}
            for run in day_runs:
                networks[run.network] = NetworkDayPerformance(
                    synthetic_recall=run.synthetic_patterns_recall,
                    novelty_validated=run.novelty_patterns_validated,
                    execution_time_seconds=run.execution_time_seconds,
                    data_correctness_passed=run.data_correctness_passed
                )
            
            day_score = (
                sum(run.synthetic_patterns_recall for run in day_runs) / len(day_runs) 
                if day_runs else 0
            )
            
            daily_performance.append(DailyPerformance(
                day_number=day_number,
                test_date=test_date,
                networks=networks,
                day_score=day_score
            ))
        
        result_info = None
        if result:
            result_info = ParticipantResult(
                rank=result.rank,
                is_winner=result.is_winner,
                final_score=result.final_score,
                beat_baseline=result.beat_baseline,
                miners_beaten=result.miners_beaten
            )
        
        return ParticipantHistoryResponse(
            tournament_id=tournament_id,
            hotkey=hotkey,
            participant_type=participant.participant_type.value,
            registration=ParticipantRegistration(
                registered_at=participant.registered_at,
                registration_order=participant.registration_order,
                github_repository=participant.github_repository,
                docker_image_tag=participant.docker_image_tag
            ),
            status=ParticipantStatusInfo(
                current_status=participant.status.value,
                is_disqualified=participant.is_disqualified,
                disqualification_reason=participant.disqualification_reason
            ),
            result=result_info,
            daily_performance=daily_performance
        )