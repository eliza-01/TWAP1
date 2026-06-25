from __future__ import annotations

API_BASE_URL = "https://futures.mexc.com/api/v1"

SUBMIT_ORDER = "/private/order/submit"
ACCOUNT_ASSET = "/private/account/asset"
OPEN_POSITIONS = "/private/position/open_positions"
TICKER = "/contract/ticker"
CONTRACT_DETAIL = "/contract/detail"

DEFAULT_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,ru;q=0.8",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "dnt": "1",
    "language": "English",
    "origin": "https://www.mexc.com",
    "pragma": "no-cache",
    "referer": "https://www.mexc.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "x-language": "en-US",
}
