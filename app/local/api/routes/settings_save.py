from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.put("")
async def save_settings(patch: dict[str, Any] = Body(...)) -> dict:
    settings = settings_store.update(patch)
    return settings.to_dict(hide_secrets=True)
