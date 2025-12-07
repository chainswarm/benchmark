from datetime import datetime
from uuid import UUID

from loguru import logger

from packages.api.models.registration_responses import (
    ParticipantStatusResponse,
    RegistrationResponse,
)
from packages.benchmark.models.tournament import (
    ParticipantStatus,
    ParticipantType,
    TournamentParticipant,
    TournamentStatus,
)
from packages.storage.repositories.miner_registry_repository import MinerRegistryRepository
from packages.storage.repositories.tournament_repository import TournamentRepository


class RegistrationService:
    
    def __init__(
        self,
        tournament_repository: TournamentRepository,
        miner_registry_repository: MinerRegistryRepository
    ):
        self.tournament_repository = tournament_repository
        self.miner_registry_repository = miner_registry_repository
    
    def register_for_tournament(
        self,
        tournament_id: UUID,
        hotkey: str
    ) -> RegistrationResponse:
        logger.info("Processing registration request", extra={
            "tournament_id": str(tournament_id),
            "hotkey": hotkey
        })
        
        tournament = self.tournament_repository.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        if tournament.status != TournamentStatus.REGISTRATION:
            raise ValueError(f"Tournament is not accepting registrations. Current status: {tournament.status.value}")
        
        miner = self.miner_registry_repository.get_miner(hotkey, tournament.image_type)
        
        if miner.status.value != 'active':
            raise ValueError(f"Miner {hotkey} is not active. Current status: {miner.status.value}")
        
        existing = self.tournament_repository.get_participant(tournament_id, hotkey)
        if existing:
            raise ValueError(f"Miner {hotkey} is already registered for this tournament")
        
        participants = self.tournament_repository.get_participants(tournament_id)
        miner_count = len([p for p in participants if p.participant_type == ParticipantType.MINER])
        if miner_count >= tournament.max_participants:
            raise ValueError(f"Tournament has reached maximum participants ({tournament.max_participants})")
        
        registration_order = self.tournament_repository.get_next_registration_order(tournament_id)
        
        participant = TournamentParticipant(
            tournament_id=tournament_id,
            hotkey=hotkey,
            participant_type=ParticipantType.MINER,
            registered_at=datetime.now(),
            registration_order=registration_order,
            github_repository=miner.github_repository,
            docker_image_tag=None,
            miner_database_name=None,
            baseline_id=None,
            status=ParticipantStatus.REGISTERED,
            updated_at=datetime.now(),
            is_disqualified=False,
            disqualification_reason=None,
            disqualified_on_day=None
        )
        
        self.tournament_repository.insert_participant(participant)
        
        logger.info("Registration successful", extra={
            "tournament_id": str(tournament_id),
            "hotkey": hotkey,
            "registration_order": registration_order
        })
        
        return RegistrationResponse(
            tournament_id=tournament_id,
            hotkey=hotkey,
            registration_order=registration_order,
            status="registered",
            registered_at=participant.registered_at
        )
    
    def get_participant_status(
        self,
        tournament_id: UUID,
        hotkey: str
    ) -> ParticipantStatusResponse:
        participant = self.tournament_repository.get_participant(tournament_id, hotkey)
        if not participant:
            raise ValueError(f"Participant {hotkey} not found in tournament {tournament_id}")
        
        return ParticipantStatusResponse(
            tournament_id=participant.tournament_id,
            hotkey=participant.hotkey,
            participant_type=participant.participant_type.value,
            registration_order=participant.registration_order,
            status=participant.status.value,
            registered_at=participant.registered_at,
            github_repository=participant.github_repository,
            docker_image_tag=participant.docker_image_tag,
            miner_database_name=participant.miner_database_name,
            is_disqualified=participant.is_disqualified,
            disqualification_reason=participant.disqualification_reason
        )
    
    def unregister_from_tournament(
        self,
        tournament_id: UUID,
        hotkey: str
    ) -> bool:
        tournament = self.tournament_repository.get_tournament_by_id(tournament_id)
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")
        
        if tournament.status != TournamentStatus.REGISTRATION:
            raise ValueError("Cannot unregister after registration period ends")
        
        participant = self.tournament_repository.get_participant(tournament_id, hotkey)
        if not participant:
            raise ValueError(f"Miner {hotkey} is not registered for this tournament")
        
        self.tournament_repository.update_participant_status(
            tournament_id,
            hotkey,
            ParticipantStatus.FAILED
        )
        
        logger.info("Unregistration successful", extra={
            "tournament_id": str(tournament_id),
            "hotkey": hotkey
        })
        
        return True