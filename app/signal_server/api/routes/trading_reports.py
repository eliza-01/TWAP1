from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from app.signal_server.api.deps import account_repository, auto_trade_report_repository
from app.signal_server.auth import bearer_token_from_request, require_http_session

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.post("/skip-reports")
async def save_skip_report(request: Request, payload: dict[str, Any] = Body(...)) -> dict:
    session = _require_report_session(request)
    return auto_trade_report_repository.save_skip_report(session, payload)


@router.get("/skip-reports")
async def list_skip_reports(request: Request, limit: int = 100) -> dict:
    session = require_http_session(request)
    return {"items": auto_trade_report_repository.list_skip_reports(session, limit)}


def _require_report_session(request: Request) -> dict[str, Any]:
    # Отчеты о пропущенных сделках могут приходить пачкой, поэтому не используем
    # pending-rate-limit с минимальной паузой между запросами. Глобальный лимит
    # middleware остается активным, а токен сессии проверяется тем же репозиторием.
    token = bearer_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Не указан токен сессии")
    session = account_repository.validate_session_token(token, require_active_access=True)
    if not session:
        raise HTTPException(status_code=401, detail="Сессия недействительна, истекла или аккаунт не активирован")
    return session
