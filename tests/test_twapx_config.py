from app.groups.twapx.config import _parse_chat_thread_map, _parse_sources, _parse_target, load_config


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


def test_parse_sources_supports_chat_with_and_without_thread():
    source_chat_ids, threads = _parse_sources("-1003918218733:2,-1003918218734:3,-1003918218735,-1003918218736,-1003918218737:1")

    assert source_chat_ids == [-1003918218733, -1003918218734, -1003918218735, -1003918218736, -1003918218737]
    assert threads == {
        -1003918218733: {2},
        -1003918218734: {3},
        -1003918218737: {1},
    }


def test_parse_target_supports_target_without_thread():
    assert _parse_target("-1003918218733") == (-1003918218733, None)


def test_parse_target_supports_target_with_thread():
    assert _parse_target("-1003918218733:4") == (-1003918218733, 4)


def test_load_config_uses_stage_specific_twapx_sources(monkeypatch):
    monkeypatch.setenv("STAGE", "ON")
    monkeypatch.setenv("STAGE_TWAPX_SOURCES", "-1001:2,-1002")
    monkeypatch.setenv("STAGE_TWAPX_TARGET", "-1003:4")
    monkeypatch.setenv("PROD_TWAPX_SOURCES", "-2001:20")
    monkeypatch.setenv("PROD_TWAPX_TARGET", "-2002:21")

    config = load_config()

    assert config.source_chat_ids == [-1001, -1002]
    assert config.source_threads_by_chat_id == {-1001: {2}}
    assert config.target_chat_id == -1003
    assert config.target_thread_id == 4


def test_load_config_uses_prod_specific_twapx_sources(monkeypatch):
    monkeypatch.setenv("STAGE", "OFF")
    monkeypatch.setenv("STAGE_TWAPX_SOURCES", "-1001:2")
    monkeypatch.setenv("STAGE_TWAPX_TARGET", "-1003:4")
    monkeypatch.setenv("PROD_TWAPX_SOURCES", "-2001:20,-2002")
    monkeypatch.setenv("PROD_TWAPX_TARGET", "-2003")

    config = load_config()

    assert config.source_chat_ids == [-2001, -2002]
    assert config.source_threads_by_chat_id == {-2001: {20}}
    assert config.target_chat_id == -2003
    assert config.target_thread_id is None
