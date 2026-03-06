"""Signals API routes"""
from fastapi import APIRouter
from models import SignalResponse
from app.logging import log_event
from services.trading_engine import generate_signals
router = APIRouter(tags=["signals"])


@router.get("/api/signals", response_model=SignalResponse)
async def get_signals():
    """Fetch real trading signals."""
    log_event("Generating signals via API...", "info")
    signals = await generate_signals()
    return SignalResponse(signals=signals)
