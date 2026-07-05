from __future__ import annotations

import argparse
import asyncio
import logging

import uvicorn

from app.core.env import load_settings
from app.db.connection import init_pool
from app.db.migrations import migrate
from app.db.repositories import MessageRepository, SourceGroupRepository
from app.groups.registry import load_processors
from app.telegram.runtime import TelegramRuntime


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="TWAP Telegram parser / local trading client")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="Create/refresh Telegram user session")
    sub.add_parser("listen", help="Listen new Telegram messages")

    history = sub.add_parser("history", help="Import recent source-channel history")
    history.add_argument("--limit", type=int, default=None)

    local = sub.add_parser("local", help="Start local web UI with exchange adapters")
    local.add_argument("--host", default="0.0.0.0")
    local.add_argument("--port", type=int, default=8080)

    signal_server = sub.add_parser("signal-server", help="Start central signal HTTP/WebSocket server")
    signal_server.add_argument("--host", default="0.0.0.0")
    signal_server.add_argument("--port", type=int, default=8090)

    args = parser.parse_args()

    settings = load_settings()

    if args.command == "local":
        init_pool(settings.db)
        migrate()
        uvicorn.run("app.local.api.app_factory:create_local_app", host=args.host, port=args.port, factory=True)
        return

    init_pool(settings.db)
    migrate()

    if args.command == "signal-server":
        uvicorn.run("app.signal_server.api.app_factory:create_signal_server_app", host=args.host, port=args.port, factory=True)
        return

    processors = load_processors(settings.groups)
    runtime = TelegramRuntime(
        settings=settings,
        processors=processors,
        message_repo=MessageRepository(),
        group_repo=SourceGroupRepository(),
    )

    if args.command == "login":
        asyncio.run(runtime.login())
    elif args.command == "listen":
        asyncio.run(runtime.listen())
    elif args.command == "history":
        asyncio.run(runtime.import_history(args.limit or settings.history_limit))


if __name__ == "__main__":
    main()
