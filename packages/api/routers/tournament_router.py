import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from clickhouse_connect import get_client

from packages.api.models.tournament_responses import (
    LeaderboardResponse,
    ParticipantHistoryResponse,
    TournamentDayResponse,
    TournamentDetailsResponse,
    TournamentsListResponse,
)
from packages.api.services.tournament_service import TournamentService
from packages.storage.repositories.tournament_repository import TournamentRepository
from packages.storage.repositories.baseline_repository import BaselineRepository


router = APIRouter(prefix="/api/v1/tournaments", tags=["tournaments"])


def get_tournament_service() -> TournamentService:
    host = os.environ.get('CLICKHOUSE_HOST', 'localhost')
    port = int(os.environ.get('CLICKHOUSE_PORT', 8123))
    client = get_client(host=host, port=port)
    tournament_repository = TournamentRepository(client)
    baseline_repository = BaselineRepository(client)
    return TournamentService(tournament_repository, baseline_repository)


@router.get("", response_model=TournamentsListResponse)
async def list_tournaments(
    image_type: Optional[str] = Query(None, pattern="^(analytics|ml)$"),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: TournamentService = Depends(get_tournament_service),
) -> TournamentsListResponse:
    return service.list_tournaments(
        image_type=image_type,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/{tournament_id}", response_model=TournamentDetailsResponse)
async def get_tournament_details(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> TournamentDetailsResponse:
    try:
        return service.get_tournament_details(tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tournament_id}/leaderboard", response_model=LeaderboardResponse)
async def get_tournament_leaderboard(
    tournament_id: UUID,
    service: TournamentService = Depends(get_tournament_service),
) -> LeaderboardResponse:
    try:
        return service.get_leaderboard(tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tournament_id}/days/{day_number}", response_model=TournamentDayResponse)
async def get_tournament_day(
    tournament_id: UUID,
    day_number: int,
    service: TournamentService = Depends(get_tournament_service),
) -> TournamentDayResponse:
    try:
        return service.get_tournament_day(tournament_id, day_number)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{tournament_id}/participants/{hotkey}",
    response_model=ParticipantHistoryResponse,
)
async def get_participant_history(
    tournament_id: UUID,
    hotkey: str,
    service: TournamentService = Depends(get_tournament_service),
) -> ParticipantHistoryResponse:
    try:
        return service.get_participant_history(tournament_id, hotkey)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))