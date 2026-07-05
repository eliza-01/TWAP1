from __future__ import annotations


class ExchangeError(Exception):
    pass


class ExchangeNotConfiguredError(ExchangeError):
    pass


class ExchangeDisabledError(ExchangeError):
    pass


class ExchangeRequestError(ExchangeError):
    pass
