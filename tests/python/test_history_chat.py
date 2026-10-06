"""Tests for the payload history chat_id grouping (search payloads by chat).

Covers:
- append stores chat_id (trimmed, capped, empty -> None).
- list_rows(chat_id=...) filters and reports the MATCHED total.
- list_rows() without chat_id is unchanged (all rows).
- preview rows expose chat_id.
- history.set_current_chat_id / get_current_chat_id round-trip + TTL.
"""

from __future__ import annotations

import pytest

from runctx import history as history_mod


@pytest.fixture
def isolated_history(tmp_path, monkeypatch):
    """Point history storage into tmp_path so tests never touch real state."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    hist_file = state_dir / "payload_history.json"
    cap_file = state_dir / "watchctx.history-cap"

    monkeypatch.setattr(history_mod, "STATE_DIR", state_dir)
    monkeypatch.setattr(history_mod, "HISTORY_FILE", hist_file)
    monkeypatch.setattr(history_mod, "HISTORY_CAP_FILE", cap_file)
    # Reset the module cache so each test starts from an empty file.
    monkeypatch.setattr(history_mod, "_cache", None)
    # Reset the current chat id (module-global) between tests.
    monkeypatch.setattr(history_mod, "_current_chat", {"chat_id": None, "ts": 0})
    return {"dir": state_dir, "history": hist_file, "cap": cap_file}


def _append(pid: int, chat_id=None, tool: str = "shell", status: str = "success") -> None:
    history_mod.append(
        payload_id=pid,
        tool=tool,
        payload_preview=f'{{"id": {pid}}}',
        result_preview="ok",
        status=status,
        duration_ms=5,
        chat_id=chat_id,
    )


# ============ append / row schema ============


def test_append_stores_chat_id(isolated_history):
    _append(1, chat_id="chat-abc")
    rows = history_mod.list_rows(limit=10)["rows"]
    assert len(rows) == 1
    assert rows[0]["chat_id"] == "chat-abc"


def test_append_normalizes_empty_chat_id_to_none(isolated_history):
    _append(1, chat_id="   ")
    _append(2, chat_id=None)
    rows = history_mod.list_rows(limit=10)["rows"]
    assert all(r["chat_id"] is None for r in rows)


def test_append_trims_and_caps_chat_id(isolated_history):
    _append(1, chat_id="  chat-x  ")
    rows = history_mod.list_rows(limit=10)["rows"]
    assert rows[0]["chat_id"] == "chat-x"

    long_id = "z" * 500
    _append(2, chat_id=long_id)
    rows = history_mod.list_rows(limit=10)["rows"]
    # newest first -> row for pid 2 is at index 0
    assert len(rows[0]["chat_id"]) == 256


# ============ list_rows filter ============


def test_list_rows_filters_by_chat_id(isolated_history):
    _append(1, chat_id="chat-a")
    _append(2, chat_id="chat-b")
    _append(3, chat_id="chat-a")
    _append(4, chat_id=None)

    out = history_mod.list_rows(limit=10, chat_id="chat-a")
    assert out["total"] == 2
    assert out["chat_id"] == "chat-a"
    assert {r["id"] for r in out["rows"]} == {1, 3}


def test_list_rows_no_filter_returns_all(isolated_history):
    _append(1, chat_id="chat-a")
    _append(2, chat_id="chat-b")
    _append(3, chat_id=None)

    out = history_mod.list_rows(limit=10)
    assert out["total"] == 3
    assert out["chat_id"] is None


def test_list_rows_filter_empty_string_is_all(isolated_history):
    _append(1, chat_id="chat-a")
    _append(2, chat_id=None)

    out = history_mod.list_rows(limit=10, chat_id="")
    assert out["total"] == 2
    assert out["chat_id"] is None


def test_list_rows_unknown_chat_returns_empty(isolated_history):
    _append(1, chat_id="chat-a")
    out = history_mod.list_rows(limit=10, chat_id="nope")
    assert out["total"] == 0
    assert out["rows"] == []
    assert out["chat_id"] == "nope"


def test_list_rows_filter_respects_limit_and_offset(isolated_history):
    for i in range(5):
        _append(i + 1, chat_id="chat-a")
    _append(99, chat_id="chat-b")

    # newest first: 5,4,3,2,1 for chat-a
    page1 = history_mod.list_rows(limit=2, offset=0, chat_id="chat-a")
    page2 = history_mod.list_rows(limit=2, offset=2, chat_id="chat-a")
    assert page1["total"] == 5
    assert [r["id"] for r in page1["rows"]] == [5, 4]
    assert [r["id"] for r in page2["rows"]] == [3, 2]


# ============ get_row still full ============


def test_get_row_returns_full_row_with_chat_id(isolated_history):
    _append(7, chat_id="chat-z")
    row = history_mod.get_row(7)
    assert row is not None
    assert row["chat_id"] == "chat-z"
    assert row["payload"] == '{"id": 7}'


# ============ current chat id (set by POST /chat) ============


def test_set_current_chat_id_stores_value(isolated_history):
    stored = history_mod.set_current_chat_id("chat-123")
    assert stored == "chat-123"
    assert history_mod.get_current_chat_id() == "chat-123"


def test_set_current_chat_id_empty_clears(isolated_history):
    history_mod.set_current_chat_id("chat-123")
    history_mod.set_current_chat_id(None)
    assert history_mod.get_current_chat_id() is None

    history_mod.set_current_chat_id("chat-123")
    history_mod.set_current_chat_id("")
    assert history_mod.get_current_chat_id() is None


def test_get_current_chat_id_none_when_never_set(isolated_history):
    history_mod.set_current_chat_id(None)
    assert history_mod.get_current_chat_id() is None


def test_get_current_chat_id_ttl_expired_returns_none(isolated_history):
    history_mod.set_current_chat_id("chat-ttl")
    # Negative max_age => age_ms (>= 0) is always > max_age => expired, even
    # when the assertion runs in the same millisecond as set_current_chat_id.
    assert history_mod.get_current_chat_id(max_age_ms=-1) is None


def test_get_current_chat_id_trims_and_caps(isolated_history):
    history_mod.set_current_chat_id("   chat-trim   ")
    assert history_mod.get_current_chat_id() == "chat-trim"

    history_mod.set_current_chat_id("q" * 400)
    got = history_mod.get_current_chat_id()
    assert got is not None and len(got) == 256
