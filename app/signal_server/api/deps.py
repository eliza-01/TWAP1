from __future__ import annotations

from app.signal_server.repositories.signals import SignalRepository
from app.signal_server.runtime.hub import SignalHub

signal_repository = SignalRepository()
signal_hub = SignalHub(signal_repository)
