from __future__ import annotations

import asyncio
import json

from starlette.websockets import WebSocketDisconnect

from app.signal_server.runtime.hub import SignalHub


class FakeRepository:
    def __init__(self) -> None:
        self.pending_calls = 0
        self.pending_after_id = None

    def max_signal_id(self) -> int:
        return 645

    def max_signal_id_before(self, boundary) -> int:
        return 640

    def list_pending(self, after_id: int, *args, **kwargs):
        self.pending_calls += 1
        self.pending_after_id = after_id
        return []


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent = []
        self._received = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if not self._received:
            self._received = True
            return json.dumps({"type": "hello", "last_signal_id": 8, "fresh_start": True, "fresh_start_after": "2026-07-06T16:00:00+00:00"})
        raise WebSocketDisconnect()

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.sent.append({"type": "close", "code": code})


def test_signal_hub_fresh_start_skips_pending() -> None:
    repository = FakeRepository()
    hub = SignalHub(repository)
    websocket = FakeWebSocket()

    asyncio.run(hub.connect(websocket))

    assert websocket.accepted is True
    assert repository.pending_calls == 1
    assert repository.pending_after_id == 640
    assert websocket.sent == [
        {
            "type": "hello.ack",
            "fresh_start": True,
            "last_signal_id": 640,
            "pending_skipped": True,
        }
    ]
    assert hub.last_signal_id == 640



class FakeRepositoryWithSmallDb:
    def __init__(self) -> None:
        self.pending_calls = 0
        self.pending_after_id = None

    def max_signal_id(self) -> int:
        return 25

    def max_signal_id_before(self, boundary) -> int:
        return 20

    def list_pending(self, after_id: int, *args, **kwargs):
        self.pending_calls += 1
        self.pending_after_id = after_id
        return []


class FakeWebSocketWithStaleLastId(FakeWebSocket):
    async def receive_text(self) -> str:
        if not self._received:
            self._received = True
            return json.dumps(
                {
                    "type": "hello",
                    "last_signal_id": 999,
                    "fresh_start": True,
                    "fresh_start_after": "2026-07-06T16:00:00+00:00",
                }
            )
        raise WebSocketDisconnect()


def test_signal_hub_fresh_start_ignores_stale_local_last_signal_id() -> None:
    repository = FakeRepositoryWithSmallDb()
    hub = SignalHub(repository)
    websocket = FakeWebSocketWithStaleLastId()

    asyncio.run(hub.connect(websocket))

    assert websocket.accepted is True
    assert repository.pending_calls == 1
    assert repository.pending_after_id == 20
    assert websocket.sent == [
        {
            "type": "hello.ack",
            "fresh_start": True,
            "last_signal_id": 20,
            "pending_skipped": True,
        }
    ]
    assert hub.last_signal_id == 20
