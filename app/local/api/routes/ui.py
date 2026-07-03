from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.local.ui.page import render_page

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(render_page())
