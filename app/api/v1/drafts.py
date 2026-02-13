"""Drafts REST API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import get_current_api_key
from app.services.draft_store import DraftStore, get_draft_store

router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftResponse(BaseModel):
    """Draft response model."""

    id: str
    content_item_id: str
    source_id: str
    title: str
    body: str
    original_url: str
    evaluation_score: float
    evaluation_reason: str
    created_at: datetime
    status: Literal["pending", "approved", "rejected", "published"]
    metadata: dict[str, Any]


@router.get("", response_model=List[DraftResponse])
async def list_drafts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    draft_store: DraftStore = Depends(get_draft_store),
    _api_key: str = Depends(get_current_api_key),
) -> List[DraftResponse]:
    """List generated drafts ordered by creation time (newest first)."""
    drafts = await draft_store.list_drafts(limit=limit, offset=offset)
    return [DraftResponse(**d.model_dump()) for d in drafts]


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: str,
    draft_store: DraftStore = Depends(get_draft_store),
    _api_key: str = Depends(get_current_api_key),
) -> DraftResponse:
    """Get a single draft by ID."""
    draft = await draft_store.get(draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    return DraftResponse(**draft.model_dump())
