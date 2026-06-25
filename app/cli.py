from __future__ import annotations

import argparse
import asyncio
import logging

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

    parser = argparse.ArgumentParser(description="TWAP Telegram parser")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="Create/refresh Telegram user session")
    sub.add_parser("listen", help="Listen new Telegram messages")
    history = sub.add_parser("history", help="Import recent source-channel history")
    history.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = load_settings()
    processors = load_processors(settings.groups)
    init_pool(settings.db)
    migrate()

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
