import os
from uuid import UUID

from clickhouse_connect import get_client
from fastapi import APIRouter, Depends, Header, HTTPException, status

from packages.api.models.registration_responses import (
    ParticipantStatusResponse,
    RegistrationErrorResponse,
    RegistrationRequest,
    RegistrationResponse,
)
from packages.api.services.registration_service import RegistrationService
from packages.storage.repositories.miner_registry_repository import MinerRegistryRepository
from packages.storage.repositories.tournament_repository import TournamentRepository

router = APIRouter(prefix="/api/internal", tags=["registration"])

REGISTRATION_API_KEY = os.environ.get('REGISTRATION_API_KEY', 'dev-key-change-me')


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != REGISTRATION_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Invalid API key"}
        )


def get_registration_service() -> RegistrationService:
    host = os.environ.get('CLICKHOUSE_HOST', 'localhost')
    port = int(os.environ.get('CLICKHOUSE_PORT', 8123))
    client = get_client(host=host, port=port)
    tournament_repository = TournamentRepository(client)
    miner_registry_repository = MinerRegistryRepository(client)
    return RegistrationService(tournament_repository, miner_registry_repository)


@router.post(
    "/tournaments/{tournament_id}/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": RegistrationErrorResponse},
        400: {"model": RegistrationErrorResponse},
    }
)
async def register_for_tournament(
    tournament_id: UUID,
    request: RegistrationRequest,
    _: None = Depends(verify_api_key),
    service: RegistrationService = Depends(get_registration_service),
):
    try:
        return service.register_for_tournament(tournament_id, request.hotkey)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "REGISTRATION_ERROR", "message": str(e)}
        )


@router.get(
    "/tournaments/{tournament_id}/participants/{hotkey}",
    response_model=ParticipantStatusResponse,
    responses={
        401: {"model": RegistrationErrorResponse},
        400: {"model": RegistrationErrorResponse},
    }
)
async def get_participant_status(
    tournament_id: UUID,
    hotkey: str,
    _: None = Depends(verify_api_key),
    service: RegistrationService = Depends(get_registration_service),
):
    try:
        return service.get_participant_status(tournament_id, hotkey)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "NOT_FOUND", "message": str(e)}
        )


@router.delete(
    "/tournaments/{tournament_id}/participants/{hotkey}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": RegistrationErrorResponse},
        400: {"model": RegistrationErrorResponse},
    }
)
async def unregister_from_tournament(
    tournament_id: UUID,
    hotkey: str,
    _: None = Depends(verify_api_key),
    service: RegistrationService = Depends(get_registration_service),
):
    try:
        service.unregister_from_tournament(tournament_id, hotkey)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "UNREGISTER_ERROR", "message": str(e)}
        )