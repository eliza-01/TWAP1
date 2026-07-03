from app.groups.twapx.config import _parse_chat_thread_map


def test_parse_chat_thread_map_supports_semicolon_threads(monkeypatch):
    monkeypatch.setenv("TWAPX_SOURCE_CHAT_THREADS", "-1001:4;5,-1002:9")

    assert _parse_chat_thread_map("TWAPX_SOURCE_CHAT_THREADS") == {
        -1001: {4, 5},
        -1002: {9},
    }


def test_parse_chat_thread_map_supports_comma_threads(monkeypatch):
    monkeypatch.setenv("TWAPX_SOURCE_CHAT_THREADS", "-1001:4,5,-1002:9")

    assert _parse_chat_thread_map("TWAPX_SOURCE_CHAT_THREADS") == {
        -1001: {4, 5},
        -1002: {9},
    }

