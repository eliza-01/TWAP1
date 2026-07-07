from __future__ import annotations

from app.platform.accounts.repository import AccountRepository
from app.platform.bot.telegram_bot import TelegramAccountBot
from app.signal_server.repositories.auto_trade_reports import AutoTradeReportRepository
from app.signal_server.repositories.signals import SignalRepository
from app.signal_server.runtime.hub import SignalHub

signal_repository = SignalRepository()
auto_trade_report_repository = AutoTradeReportRepository()
account_repository = AccountRepository()
signal_hub = SignalHub(signal_repository, account_repository)
telegram_account_bot = TelegramAccountBot(account_repository)
