from datetime import datetime, timezone
from decimal import Decimal

from app.db.connection import json_dump


def test_json_dump_serializes_datetime():
    dumped = json_dump({"date": datetime(2026, 6, 25, 0, 26, tzinfo=timezone.utc)})
    assert "2026-06-25T00:26:00+00:00" in dumped


def test_json_dump_serializes_common_telethon_values():
    dumped = json_dump({"bytes": b"abc", "decimal": Decimal("1.23"), "set": {2, 1}})
    assert '"bytes":"616263"' in dumped
    assert '"decimal":1.23' in dumped
    assert '"set":[1,2]' in dumped

