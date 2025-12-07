from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from clickhouse_connect.driver import Client

from chainswarm_core.db import BaseRepository, row_to_dict
from chainswarm_core.observability import log_errors

from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.epoch import BenchmarkEpoch, EpochStatus
from packages.benchmark.models.results import AnalyticsDailyRun, RunStatus
from packages.benchmark.models.tournament import (
    ParticipantStatus,
    ParticipantType,
    Tournament,
    TournamentParticipant,
    TournamentResult,
    TournamentStatus,
)


class TournamentRepository(BaseRepository):
    
    def __init__(self, client: Client):
        super().__init__(client)

    @classmethod
    def schema(cls) -> str:
        return 'benchmark/tournament_tournaments.sql'

    @classmethod
    def table_name(cls) -> str:
        return 'tournament_tournaments'

    # ==================== Tournament Operations ====================

    @log_errors
    def get_tournament_by_id(self, tournament_id: UUID) -> Optional[Tournament]:
        """Get tournament by ID."""
        query = f"""
        SELECT tournament_id, name, image_type, registration_start, registration_end,
               competition_start, competition_end, max_participants, epoch_days,
               test_networks, test_window_days, baseline_id, status, current_day,
               winner_hotkey, baseline_beaten, created_at, completed_at
        FROM {self.table_name()} FINAL
        WHERE tournament_id = %(tournament_id)s
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={'tournament_id': str(tournament_id)})
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_tournament(row, result.column_names)

    @log_errors
    def get_active_tournaments(self, image_type: Optional[ImageType] = None) -> List[Tournament]:
        """Get all tournaments that are in 'registration' or 'in_progress' status."""
        if image_type:
            query = f"""
            SELECT tournament_id, name, image_type, registration_start, registration_end,
                   competition_start, competition_end, max_participants, epoch_days,
                   test_networks, test_window_days, baseline_id, status, current_day,
                   winner_hotkey, baseline_beaten, created_at, completed_at
            FROM {self.table_name()} FINAL
            WHERE status IN ('registration', 'in_progress')
              AND image_type = %(image_type)s
            ORDER BY competition_start
            """
            result = self.client.query(query, parameters={'image_type': image_type.value})
        else:
            query = f"""
            SELECT tournament_id, name, image_type, registration_start, registration_end,
                   competition_start, competition_end, max_participants, epoch_days,
                   test_networks, test_window_days, baseline_id, status, current_day,
                   winner_hotkey, baseline_beaten, created_at, completed_at
            FROM {self.table_name()} FINAL
            WHERE status IN ('registration', 'in_progress')
            ORDER BY competition_start
            """
            result = self.client.query(query)
        
        tournaments = []
        for row in result.result_rows:
            tournaments.append(self._row_to_tournament(row, result.column_names))
        
        return tournaments

    @log_errors
    def get_tournaments_by_status(self, status: TournamentStatus) -> List[Tournament]:
        """Get all tournaments with a specific status."""
        query = f"""
        SELECT tournament_id, name, image_type, registration_start, registration_end,
               competition_start, competition_end, max_participants, epoch_days,
               test_networks, test_window_days, baseline_id, status, current_day,
               winner_hotkey, baseline_beaten, created_at, completed_at
        FROM {self.table_name()} FINAL
        WHERE status = %(status)s
        ORDER BY competition_start
        """
        
        result = self.client.query(query, parameters={'status': status.value})
        
        tournaments = []
        for row in result.result_rows:
            tournaments.append(self._row_to_tournament(row, result.column_names))
        
        return tournaments

    @log_errors
    def insert_tournament(self, tournament: Tournament) -> None:
        """Insert a new tournament."""
        query = f"""
        INSERT INTO {self.table_name()} 
        (tournament_id, name, image_type, registration_start, registration_end,
         competition_start, competition_end, max_participants, epoch_days,
         test_networks, test_window_days, baseline_id, status, current_day,
         winner_hotkey, baseline_beaten, created_at, completed_at)
        VALUES (%(tournament_id)s, %(name)s, %(image_type)s, %(registration_start)s,
                %(registration_end)s, %(competition_start)s, %(competition_end)s,
                %(max_participants)s, %(epoch_days)s, %(test_networks)s, %(test_window_days)s,
                %(baseline_id)s, %(status)s, %(current_day)s, %(winner_hotkey)s,
                %(baseline_beaten)s, %(created_at)s, %(completed_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(tournament.tournament_id),
            'name': tournament.name,
            'image_type': tournament.image_type.value,
            'registration_start': tournament.registration_start,
            'registration_end': tournament.registration_end,
            'competition_start': tournament.competition_start,
            'competition_end': tournament.competition_end,
            'max_participants': tournament.max_participants,
            'epoch_days': tournament.epoch_days,
            'test_networks': tournament.test_networks,
            'test_window_days': tournament.test_window_days,
            'baseline_id': str(tournament.baseline_id),
            'status': tournament.status.value,
            'current_day': tournament.current_day,
            'winner_hotkey': tournament.winner_hotkey,
            'baseline_beaten': tournament.baseline_beaten,
            'created_at': tournament.created_at,
            'completed_at': tournament.completed_at
        })

    @log_errors
    def update_tournament_status(
        self,
        tournament_id: UUID,
        status: TournamentStatus,
        current_day: int = None
    ) -> None:
        """Update the status of a tournament."""
        tournament = self.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament not found: {tournament_id}")
        
        new_current_day = current_day if current_day is not None else tournament.current_day
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (tournament_id, name, image_type, registration_start, registration_end,
         competition_start, competition_end, max_participants, epoch_days,
         test_networks, test_window_days, baseline_id, status, current_day,
         winner_hotkey, baseline_beaten, created_at, completed_at)
        VALUES (%(tournament_id)s, %(name)s, %(image_type)s, %(registration_start)s,
                %(registration_end)s, %(competition_start)s, %(competition_end)s,
                %(max_participants)s, %(epoch_days)s, %(test_networks)s, %(test_window_days)s,
                %(baseline_id)s, %(status)s, %(current_day)s, %(winner_hotkey)s,
                %(baseline_beaten)s, %(created_at)s, %(completed_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(tournament_id),
            'name': tournament.name,
            'image_type': tournament.image_type.value,
            'registration_start': tournament.registration_start,
            'registration_end': tournament.registration_end,
            'competition_start': tournament.competition_start,
            'competition_end': tournament.competition_end,
            'max_participants': tournament.max_participants,
            'epoch_days': tournament.epoch_days,
            'test_networks': tournament.test_networks,
            'test_window_days': tournament.test_window_days,
            'baseline_id': str(tournament.baseline_id),
            'status': status.value,
            'current_day': new_current_day,
            'winner_hotkey': tournament.winner_hotkey,
            'baseline_beaten': tournament.baseline_beaten,
            'created_at': tournament.created_at,
            'completed_at': tournament.completed_at
        })

    @log_errors
    def complete_tournament(
        self,
        tournament_id: UUID,
        winner_hotkey: str,
        baseline_beaten: bool
    ) -> None:
        """Complete a tournament with the winner and baseline status."""
        tournament = self.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament not found: {tournament_id}")
        
        query = f"""
        INSERT INTO {self.table_name()} 
        (tournament_id, name, image_type, registration_start, registration_end,
         competition_start, competition_end, max_participants, epoch_days,
         test_networks, test_window_days, baseline_id, status, current_day,
         winner_hotkey, baseline_beaten, created_at, completed_at)
        VALUES (%(tournament_id)s, %(name)s, %(image_type)s, %(registration_start)s,
                %(registration_end)s, %(competition_start)s, %(competition_end)s,
                %(max_participants)s, %(epoch_days)s, %(test_networks)s, %(test_window_days)s,
                %(baseline_id)s, %(status)s, %(current_day)s, %(winner_hotkey)s,
                %(baseline_beaten)s, %(created_at)s, %(completed_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(tournament_id),
            'name': tournament.name,
            'image_type': tournament.image_type.value,
            'registration_start': tournament.registration_start,
            'registration_end': tournament.registration_end,
            'competition_start': tournament.competition_start,
            'competition_end': tournament.competition_end,
            'max_participants': tournament.max_participants,
            'epoch_days': tournament.epoch_days,
            'test_networks': tournament.test_networks,
            'test_window_days': tournament.test_window_days,
            'baseline_id': str(tournament.baseline_id),
            'status': TournamentStatus.COMPLETED.value,
            'current_day': tournament.current_day,
            'winner_hotkey': winner_hotkey,
            'baseline_beaten': baseline_beaten,
            'created_at': tournament.created_at,
            'completed_at': datetime.now()
        })

    # ==================== Participant Operations ====================

    @log_errors
    def get_participants(self, tournament_id: UUID) -> List[TournamentParticipant]:
        """Get all participants for a tournament."""
        query = """
        SELECT tournament_id, hotkey, participant_type, registered_at, registration_order,
               github_repository, docker_image_tag, miner_database_name, baseline_id,
               status, is_disqualified, disqualification_reason, disqualified_on_day, updated_at
        FROM tournament_participants FINAL
        WHERE tournament_id = %(tournament_id)s
        ORDER BY registration_order
        """
        
        result = self.client.query(query, parameters={'tournament_id': str(tournament_id)})
        
        participants = []
        for row in result.result_rows:
            participants.append(self._row_to_participant(row, result.column_names))
        
        return participants

    @log_errors
    def get_participant(self, tournament_id: UUID, hotkey: str) -> Optional[TournamentParticipant]:
        """Get a specific participant by tournament ID and hotkey."""
        query = """
        SELECT tournament_id, hotkey, participant_type, registered_at, registration_order,
               github_repository, docker_image_tag, miner_database_name, baseline_id,
               status, is_disqualified, disqualification_reason, disqualified_on_day, updated_at
        FROM tournament_participants FINAL
        WHERE tournament_id = %(tournament_id)s AND hotkey = %(hotkey)s
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={
            'tournament_id': str(tournament_id),
            'hotkey': hotkey
        })
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_participant(row, result.column_names)

    @log_errors
    def get_next_registration_order(self, tournament_id: UUID) -> int:
        """Get the next registration order number for a tournament."""
        query = """
        SELECT max(registration_order) as max_order
        FROM tournament_participants FINAL
        WHERE tournament_id = %(tournament_id)s
        """
        
        result = self.client.query(query, parameters={'tournament_id': str(tournament_id)})
        
        if not result.result_rows or result.result_rows[0][0] is None:
            return 1
        
        return result.result_rows[0][0] + 1

    @log_errors
    def insert_participant(self, participant: TournamentParticipant) -> None:
        """Insert a new tournament participant."""
        query = """
        INSERT INTO tournament_participants
        (tournament_id, hotkey, participant_type, registered_at, registration_order,
         github_repository, docker_image_tag, miner_database_name, baseline_id,
         status, is_disqualified, disqualification_reason, disqualified_on_day, updated_at)
        VALUES (%(tournament_id)s, %(hotkey)s, %(participant_type)s, %(registered_at)s,
                %(registration_order)s, %(github_repository)s, %(docker_image_tag)s,
                %(miner_database_name)s, %(baseline_id)s, %(status)s, %(is_disqualified)s,
                %(disqualification_reason)s, %(disqualified_on_day)s, %(updated_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(participant.tournament_id),
            'hotkey': participant.hotkey,
            'participant_type': participant.participant_type.value,
            'registered_at': participant.registered_at,
            'registration_order': participant.registration_order,
            'github_repository': participant.github_repository,
            'docker_image_tag': participant.docker_image_tag,
            'miner_database_name': participant.miner_database_name,
            'baseline_id': str(participant.baseline_id) if participant.baseline_id else None,
            'status': participant.status.value,
            'is_disqualified': participant.is_disqualified,
            'disqualification_reason': participant.disqualification_reason,
            'disqualified_on_day': participant.disqualified_on_day,
            'updated_at': participant.updated_at
        })

    @log_errors
    def update_participant_status(
        self,
        tournament_id: UUID,
        hotkey: str,
        status: ParticipantStatus
    ) -> None:
        """Update the status of a tournament participant."""
        participant = self.get_participant(tournament_id, hotkey)
        if not participant:
            raise ValueError(f"Participant not found: {hotkey} in tournament {tournament_id}")
        
        now = datetime.now()
        
        query = """
        INSERT INTO tournament_participants
        (tournament_id, hotkey, participant_type, registered_at, registration_order,
         github_repository, docker_image_tag, miner_database_name, baseline_id,
         status, is_disqualified, disqualification_reason, disqualified_on_day, updated_at)
        VALUES (%(tournament_id)s, %(hotkey)s, %(participant_type)s, %(registered_at)s,
                %(registration_order)s, %(github_repository)s, %(docker_image_tag)s,
                %(miner_database_name)s, %(baseline_id)s, %(status)s, %(is_disqualified)s,
                %(disqualification_reason)s, %(disqualified_on_day)s, %(updated_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(tournament_id),
            'hotkey': hotkey,
            'participant_type': participant.participant_type.value,
            'registered_at': participant.registered_at,
            'registration_order': participant.registration_order,
            'github_repository': participant.github_repository,
            'docker_image_tag': participant.docker_image_tag,
            'miner_database_name': participant.miner_database_name,
            'baseline_id': str(participant.baseline_id) if participant.baseline_id else None,
            'status': status.value,
            'is_disqualified': participant.is_disqualified,
            'disqualification_reason': participant.disqualification_reason,
            'disqualified_on_day': participant.disqualified_on_day,
            'updated_at': now
        })

    @log_errors
    def disqualify_participant(
        self,
        tournament_id: UUID,
        hotkey: str,
        reason: str,
        day: int
    ) -> None:
        """Disqualify a tournament participant."""
        participant = self.get_participant(tournament_id, hotkey)
        if not participant:
            raise ValueError(f"Participant not found: {hotkey} in tournament {tournament_id}")
        
        now = datetime.now()
        
        query = """
        INSERT INTO tournament_participants
        (tournament_id, hotkey, participant_type, registered_at, registration_order,
         github_repository, docker_image_tag, miner_database_name, baseline_id,
         status, is_disqualified, disqualification_reason, disqualified_on_day, updated_at)
        VALUES (%(tournament_id)s, %(hotkey)s, %(participant_type)s, %(registered_at)s,
                %(registration_order)s, %(github_repository)s, %(docker_image_tag)s,
                %(miner_database_name)s, %(baseline_id)s, %(status)s, %(is_disqualified)s,
                %(disqualification_reason)s, %(disqualified_on_day)s, %(updated_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(tournament_id),
            'hotkey': hotkey,
            'participant_type': participant.participant_type.value,
            'registered_at': participant.registered_at,
            'registration_order': participant.registration_order,
            'github_repository': participant.github_repository,
            'docker_image_tag': participant.docker_image_tag,
            'miner_database_name': participant.miner_database_name,
            'baseline_id': str(participant.baseline_id) if participant.baseline_id else None,
            'status': ParticipantStatus.DISQUALIFIED.value,
            'is_disqualified': True,
            'disqualification_reason': reason,
            'disqualified_on_day': day,
            'updated_at': now
        })

    # ==================== Epoch Operations (using unified benchmark_epochs table) ====================

    @log_errors
    def get_tournament_epochs(self, tournament_id: UUID) -> List[BenchmarkEpoch]:
        """Get all epochs linked to a tournament."""
        query = """
        SELECT epoch_id, hotkey, image_type, start_date, end_date,
               status, docker_image_tag, miner_database_name, created_at, completed_at, tournament_id
        FROM benchmark_epochs
        WHERE tournament_id = %(tournament_id)s
        ORDER BY start_date
        """
        
        result = self.client.query(query, parameters={'tournament_id': str(tournament_id)})
        
        epochs = []
        for row in result.result_rows:
            epochs.append(self._row_to_benchmark_epoch(row, result.column_names))
        
        return epochs

    @log_errors
    def get_tournament_epoch_by_hotkey(
        self,
        tournament_id: UUID,
        hotkey: str
    ) -> Optional[BenchmarkEpoch]:
        """Get the epoch for a specific participant in a tournament."""
        query = """
        SELECT epoch_id, hotkey, image_type, start_date, end_date,
               status, docker_image_tag, miner_database_name, created_at, completed_at, tournament_id
        FROM benchmark_epochs
        WHERE tournament_id = %(tournament_id)s AND hotkey = %(hotkey)s
        ORDER BY start_date DESC
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={
            'tournament_id': str(tournament_id),
            'hotkey': hotkey
        })
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_benchmark_epoch(row, result.column_names)

    @log_errors
    def get_tournament_epoch(self, tournament_id: UUID) -> Optional[BenchmarkEpoch]:
        query = """
        SELECT epoch_id, hotkey, image_type, start_date, end_date,
               status, docker_image_tag, miner_database_name, created_at, completed_at, tournament_id
        FROM benchmark_epochs
        WHERE tournament_id = %(tournament_id)s
        ORDER BY start_date DESC
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={'tournament_id': str(tournament_id)})
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_benchmark_epoch(row, result.column_names)

    @log_errors
    def insert_epoch(self, epoch: BenchmarkEpoch) -> None:
        query = """
        INSERT INTO benchmark_epochs
        (epoch_id, hotkey, image_type, start_date, end_date, status,
         docker_image_tag, miner_database_name, created_at, completed_at, tournament_id)
        VALUES (%(epoch_id)s, %(hotkey)s, %(image_type)s, %(start_date)s, %(end_date)s,
                %(status)s, %(docker_image_tag)s, %(miner_database_name)s,
                %(created_at)s, %(completed_at)s, %(tournament_id)s)
        """
        
        self.client.command(query, parameters={
            'epoch_id': str(epoch.epoch_id),
            'hotkey': epoch.hotkey,
            'image_type': epoch.image_type.value,
            'start_date': epoch.start_date,
            'end_date': epoch.end_date,
            'status': epoch.status.value,
            'docker_image_tag': epoch.docker_image_tag,
            'miner_database_name': epoch.miner_database_name,
            'created_at': epoch.created_at,
            'completed_at': epoch.completed_at,
            'tournament_id': str(epoch.tournament_id) if epoch.tournament_id else None
        })

    @log_errors
    def update_epoch_status(self, epoch_id: UUID, status: EpochStatus) -> None:
        query = """
        ALTER TABLE benchmark_epochs
        UPDATE status = %(status)s
        WHERE epoch_id = %(epoch_id)s
        """
        
        self.client.command(query, parameters={
            'epoch_id': str(epoch_id),
            'status': status.value
        })

    # ==================== Daily Runs Operations (using unified benchmark_analytics_daily_runs table) ====================

    @log_errors
    def insert_analytics_daily_run(self, run: AnalyticsDailyRun) -> None:
        query = """
        INSERT INTO benchmark_analytics_daily_runs
        (run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
         execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
         synthetic_patterns_expected, synthetic_patterns_found, synthetic_patterns_recall,
         novelty_patterns_reported, novelty_patterns_validated, novelty_addresses_valid, novelty_connections_valid,
         all_addresses_exist, all_connections_exist, data_correctness_passed,
         status, error_message, created_at,
         tournament_id, participant_type, run_order, is_disqualified, disqualification_reason)
        VALUES (%(run_id)s, %(epoch_id)s, %(hotkey)s, %(test_date)s, %(network)s, %(window_days)s, %(processing_date)s,
                %(execution_time_seconds)s, %(container_exit_code)s, %(gpu_memory_peak_mb)s,
                %(synthetic_patterns_expected)s, %(synthetic_patterns_found)s, %(synthetic_patterns_recall)s,
                %(novelty_patterns_reported)s, %(novelty_patterns_validated)s, %(novelty_addresses_valid)s, %(novelty_connections_valid)s,
                %(all_addresses_exist)s, %(all_connections_exist)s, %(data_correctness_passed)s,
                %(status)s, %(error_message)s, %(created_at)s,
                %(tournament_id)s, %(participant_type)s, %(run_order)s, %(is_disqualified)s, %(disqualification_reason)s)
        """
        
        self.client.command(query, parameters={
            'run_id': str(run.run_id),
            'epoch_id': str(run.epoch_id),
            'hotkey': run.hotkey,
            'test_date': run.test_date,
            'network': run.network,
            'window_days': run.window_days,
            'processing_date': run.processing_date,
            'execution_time_seconds': run.execution_time_seconds,
            'container_exit_code': run.container_exit_code,
            'gpu_memory_peak_mb': run.gpu_memory_peak_mb,
            'synthetic_patterns_expected': run.synthetic_patterns_expected,
            'synthetic_patterns_found': run.synthetic_patterns_found,
            'synthetic_patterns_recall': run.synthetic_patterns_recall,
            'novelty_patterns_reported': run.novelty_patterns_reported,
            'novelty_patterns_validated': run.novelty_patterns_validated,
            'novelty_addresses_valid': run.novelty_addresses_valid,
            'novelty_connections_valid': run.novelty_connections_valid,
            'all_addresses_exist': run.all_addresses_exist,
            'all_connections_exist': run.all_connections_exist,
            'data_correctness_passed': run.data_correctness_passed,
            'status': run.status.value,
            'error_message': run.error_message,
            'created_at': run.created_at,
            'tournament_id': str(run.tournament_id) if run.tournament_id else None,
            'participant_type': run.participant_type,
            'run_order': run.run_order,
            'is_disqualified': run.is_disqualified,
            'disqualification_reason': run.disqualification_reason
        })

    @log_errors
    def update_analytics_daily_run_status(self, run_id: UUID, status: RunStatus) -> None:
        query = """
        ALTER TABLE benchmark_analytics_daily_runs
        UPDATE status = %(status)s
        WHERE run_id = %(run_id)s
        """
        
        self.client.command(query, parameters={
            'run_id': str(run_id),
            'status': status.value
        })

    @log_errors
    def get_daily_runs_for_tournament(
        self,
        tournament_id: UUID,
        test_date: date = None
    ) -> List[AnalyticsDailyRun]:
        """Get all daily runs for a tournament, optionally filtered by date."""
        query = """
        SELECT run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
               execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
               synthetic_patterns_expected, synthetic_patterns_found, synthetic_patterns_recall,
               novelty_patterns_reported, novelty_patterns_validated, novelty_addresses_valid, novelty_connections_valid,
               all_addresses_exist, all_connections_exist, data_correctness_passed,
               status, error_message, created_at,
               tournament_id, participant_type, run_order, is_disqualified, disqualification_reason
        FROM benchmark_analytics_daily_runs
        WHERE tournament_id = %(tournament_id)s
        """
        
        params = {'tournament_id': str(tournament_id)}
        
        if test_date:
            query += " AND test_date = %(test_date)s"
            params['test_date'] = test_date
        
        query += " ORDER BY test_date, run_order"
        
        result = self.client.query(query, parameters=params)
        
        runs = []
        for row in result.result_rows:
            runs.append(self._row_to_analytics_daily_run(row, result.column_names))
        
        return runs

    @log_errors
    def get_participant_runs(self, tournament_id: UUID, hotkey: str) -> List[AnalyticsDailyRun]:
        """Get all runs for a specific participant in a tournament."""
        query = """
        SELECT run_id, epoch_id, hotkey, test_date, network, window_days, processing_date,
               execution_time_seconds, container_exit_code, gpu_memory_peak_mb,
               synthetic_patterns_expected, synthetic_patterns_found, synthetic_patterns_recall,
               novelty_patterns_reported, novelty_patterns_validated, novelty_addresses_valid, novelty_connections_valid,
               all_addresses_exist, all_connections_exist, data_correctness_passed,
               status, error_message, created_at,
               tournament_id, participant_type, run_order, is_disqualified, disqualification_reason
        FROM benchmark_analytics_daily_runs
        WHERE tournament_id = %(tournament_id)s AND hotkey = %(hotkey)s
        ORDER BY test_date, run_order
        """
        
        result = self.client.query(query, parameters={
            'tournament_id': str(tournament_id),
            'hotkey': hotkey
        })
        
        runs = []
        for row in result.result_rows:
            runs.append(self._row_to_analytics_daily_run(row, result.column_names))
        
        return runs

    @log_errors
    def get_daily_runs_by_date(self, tournament_id: UUID, test_date: date) -> List[AnalyticsDailyRun]:
        """Get all daily runs for a tournament on a specific date (backward compatible)."""
        return self.get_daily_runs_for_tournament(tournament_id, test_date)

    # ==================== Results Operations ====================

    @log_errors
    def get_results(self, tournament_id: UUID) -> List[TournamentResult]:
        """Get all results for a tournament."""
        query = """
        SELECT tournament_id, hotkey, participant_type, pattern_accuracy_score,
               data_correctness_score, performance_score, final_score,
               data_correctness_all_days, all_runs_within_time_limit, days_completed,
               total_runs_completed, average_execution_time_seconds, baseline_comparison_ratio,
               rank, is_winner, beat_baseline, miners_beaten, calculated_at
        FROM tournament_results FINAL
        WHERE tournament_id = %(tournament_id)s
        ORDER BY rank
        """
        
        result = self.client.query(query, parameters={'tournament_id': str(tournament_id)})
        
        results = []
        for row in result.result_rows:
            results.append(self._row_to_result(row, result.column_names))
        
        return results

    @log_errors
    def get_result(self, tournament_id: UUID, hotkey: str) -> Optional[TournamentResult]:
        """Get the result for a specific participant in a tournament."""
        query = """
        SELECT tournament_id, hotkey, participant_type, pattern_accuracy_score,
               data_correctness_score, performance_score, final_score,
               data_correctness_all_days, all_runs_within_time_limit, days_completed,
               total_runs_completed, average_execution_time_seconds, baseline_comparison_ratio,
               rank, is_winner, beat_baseline, miners_beaten, calculated_at
        FROM tournament_results FINAL
        WHERE tournament_id = %(tournament_id)s AND hotkey = %(hotkey)s
        LIMIT 1
        """
        
        result = self.client.query(query, parameters={
            'tournament_id': str(tournament_id),
            'hotkey': hotkey
        })
        
        if not result.result_rows:
            return None
        
        row = result.result_rows[0]
        return self._row_to_result(row, result.column_names)

    @log_errors
    def insert_result(self, result: TournamentResult) -> None:
        """Insert a tournament result."""
        query = """
        INSERT INTO tournament_results 
        (tournament_id, hotkey, participant_type, pattern_accuracy_score,
         data_correctness_score, performance_score, final_score,
         data_correctness_all_days, all_runs_within_time_limit, days_completed,
         total_runs_completed, average_execution_time_seconds, baseline_comparison_ratio,
         rank, is_winner, beat_baseline, miners_beaten, calculated_at)
        VALUES (%(tournament_id)s, %(hotkey)s, %(participant_type)s, %(pattern_accuracy_score)s,
                %(data_correctness_score)s, %(performance_score)s, %(final_score)s,
                %(data_correctness_all_days)s, %(all_runs_within_time_limit)s, %(days_completed)s,
                %(total_runs_completed)s, %(average_execution_time_seconds)s, %(baseline_comparison_ratio)s,
                %(rank)s, %(is_winner)s, %(beat_baseline)s, %(miners_beaten)s, %(calculated_at)s)
        """
        
        self.client.command(query, parameters={
            'tournament_id': str(result.tournament_id),
            'hotkey': result.hotkey,
            'participant_type': result.participant_type.value,
            'pattern_accuracy_score': result.pattern_accuracy_score,
            'data_correctness_score': result.data_correctness_score,
            'performance_score': result.performance_score,
            'final_score': result.final_score,
            'data_correctness_all_days': result.data_correctness_all_days,
            'all_runs_within_time_limit': result.all_runs_within_time_limit,
            'days_completed': result.days_completed,
            'total_runs_completed': result.total_runs_completed,
            'average_execution_time_seconds': result.average_execution_time_seconds,
            'baseline_comparison_ratio': result.baseline_comparison_ratio,
            'rank': result.rank,
            'is_winner': result.is_winner,
            'beat_baseline': result.beat_baseline,
            'miners_beaten': result.miners_beaten,
            'calculated_at': result.calculated_at
        })

    # ==================== Row Conversion Helpers ====================

    def _row_to_tournament(self, row, column_names) -> Tournament:
        """Convert a database row to a Tournament model."""
        data = row_to_dict(row, column_names)
        return Tournament(
            tournament_id=UUID(data['tournament_id']) if isinstance(data['tournament_id'], str) else data['tournament_id'],
            name=data['name'],
            image_type=ImageType(data['image_type']),
            registration_start=data['registration_start'],
            registration_end=data['registration_end'],
            competition_start=data['competition_start'],
            competition_end=data['competition_end'],
            max_participants=data['max_participants'],
            epoch_days=data['epoch_days'],
            test_networks=list(data['test_networks']) if data['test_networks'] else [],
            test_window_days=list(data['test_window_days']) if data['test_window_days'] else [],
            baseline_id=UUID(data['baseline_id']) if isinstance(data['baseline_id'], str) else data['baseline_id'],
            status=TournamentStatus(data['status']),
            current_day=data['current_day'],
            winner_hotkey=data['winner_hotkey'],
            baseline_beaten=data['baseline_beaten'],
            created_at=data['created_at'],
            completed_at=data['completed_at']
        )

    def _row_to_participant(self, row, column_names) -> TournamentParticipant:
        """Convert a database row to a TournamentParticipant model."""
        data = row_to_dict(row, column_names)
        return TournamentParticipant(
            tournament_id=UUID(data['tournament_id']) if isinstance(data['tournament_id'], str) else data['tournament_id'],
            hotkey=data['hotkey'],
            participant_type=ParticipantType(data['participant_type']),
            registered_at=data['registered_at'],
            registration_order=data['registration_order'],
            github_repository=data['github_repository'],
            docker_image_tag=data['docker_image_tag'],
            miner_database_name=data['miner_database_name'],
            baseline_id=UUID(data['baseline_id']) if data['baseline_id'] else None,
            status=ParticipantStatus(data['status']),
            is_disqualified=data.get('is_disqualified', False),
            disqualification_reason=data.get('disqualification_reason'),
            disqualified_on_day=data.get('disqualified_on_day'),
            updated_at=data['updated_at']
        )

    def _row_to_benchmark_epoch(self, row, column_names) -> BenchmarkEpoch:
        """Convert a database row to a BenchmarkEpoch model."""
        data = row_to_dict(row, column_names)
        return BenchmarkEpoch(
            epoch_id=UUID(data['epoch_id']) if isinstance(data['epoch_id'], str) else data['epoch_id'],
            hotkey=data['hotkey'],
            image_type=ImageType(data['image_type']),
            start_date=data['start_date'],
            end_date=data['end_date'],
            status=EpochStatus(data['status']),
            docker_image_tag=data['docker_image_tag'],
            miner_database_name=data['miner_database_name'],
            created_at=data['created_at'],
            completed_at=data.get('completed_at'),
            tournament_id=UUID(data['tournament_id']) if data.get('tournament_id') else None
        )

    def _row_to_analytics_daily_run(self, row, column_names) -> AnalyticsDailyRun:
        """Convert a database row to an AnalyticsDailyRun model."""
        data = row_to_dict(row, column_names)
        return AnalyticsDailyRun(
            run_id=UUID(data['run_id']) if isinstance(data['run_id'], str) else data['run_id'],
            epoch_id=UUID(data['epoch_id']) if isinstance(data['epoch_id'], str) else data['epoch_id'],
            hotkey=data['hotkey'],
            test_date=data['test_date'],
            network=data['network'],
            window_days=data['window_days'],
            processing_date=data['processing_date'],
            execution_time_seconds=data['execution_time_seconds'],
            container_exit_code=data['container_exit_code'],
            gpu_memory_peak_mb=data['gpu_memory_peak_mb'],
            synthetic_patterns_expected=data['synthetic_patterns_expected'],
            synthetic_patterns_found=data['synthetic_patterns_found'],
            synthetic_patterns_recall=data['synthetic_patterns_recall'],
            novelty_patterns_reported=data['novelty_patterns_reported'],
            novelty_patterns_validated=data['novelty_patterns_validated'],
            novelty_addresses_valid=data['novelty_addresses_valid'],
            novelty_connections_valid=data['novelty_connections_valid'],
            all_addresses_exist=data['all_addresses_exist'],
            all_connections_exist=data['all_connections_exist'],
            data_correctness_passed=data['data_correctness_passed'],
            status=RunStatus(data['status']),
            error_message=data.get('error_message'),
            created_at=data['created_at'],
            tournament_id=UUID(data['tournament_id']) if data.get('tournament_id') else None,
            participant_type=data.get('participant_type', 'miner'),
            run_order=data.get('run_order', 0),
            is_disqualified=data.get('is_disqualified', False),
            disqualification_reason=data.get('disqualification_reason')
        )

    def _row_to_result(self, row, column_names) -> TournamentResult:
        """Convert a database row to a TournamentResult model."""
        data = row_to_dict(row, column_names)
        return TournamentResult(
            tournament_id=UUID(data['tournament_id']) if isinstance(data['tournament_id'], str) else data['tournament_id'],
            hotkey=data['hotkey'],
            participant_type=ParticipantType(data['participant_type']),
            pattern_accuracy_score=data['pattern_accuracy_score'],
            data_correctness_score=data['data_correctness_score'],
            performance_score=data['performance_score'],
            final_score=data['final_score'],
            data_correctness_all_days=data['data_correctness_all_days'],
            all_runs_within_time_limit=data['all_runs_within_time_limit'],
            days_completed=data['days_completed'],
            total_runs_completed=data['total_runs_completed'],
            average_execution_time_seconds=data['average_execution_time_seconds'],
            baseline_comparison_ratio=data['baseline_comparison_ratio'],
            rank=data['rank'],
            is_winner=data['is_winner'],
            beat_baseline=data['beat_baseline'],
            miners_beaten=data['miners_beaten'],
            calculated_at=data['calculated_at']
        )