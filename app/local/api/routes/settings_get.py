from __future__ import annotations

from fastapi import APIRouter
from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("")
async def get_settings() -> dict:
    return settings_store.load().to_dict(hide_secrets=True)
