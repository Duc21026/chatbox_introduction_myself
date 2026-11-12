import backend.session as session_module
from backend.session import MAX_SHOWN_IDS, SessionStore


def test_session_reuses_id_and_caps_shown_ids(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(session_module.time, "monotonic", lambda: clock[0])
    store = SessionStore(ttl=10, max_sessions=5)

    session_id, state = store.get_or_create("s-abc")
    assert session_id == "s-abc"
    state.add_shown(f"id-{index}" for index in range(MAX_SHOWN_IDS + 20))
    assert len(state.shown_ids) == MAX_SHOWN_IDS
    assert state.shown_ids[-1] == f"id-{MAX_SHOWN_IDS + 19}"


def test_session_expires(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(session_module.time, "monotonic", lambda: clock[0])
    store = SessionStore(ttl=10, max_sessions=5)

    session_id, _ = store.get_or_create()
    assert store.get(session_id) is not None
    clock[0] += 11
    assert store.get(session_id) is None
    assert store.expire() == 0


def test_session_evicts_oldest(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(session_module.time, "monotonic", lambda: clock[0])
    store = SessionStore(ttl=1000, max_sessions=2)

    store.get_or_create("one")
    clock[0] += 1
    store.get_or_create("two")
    clock[0] += 1
    store.get_or_create("three")

    assert store.count() == 2
    assert store.get("one") is None
    assert store.get("two") is not None
    assert store.get("three") is not None


def test_new_session_id_is_generated():
    store = SessionStore(ttl=10, max_sessions=5)
    session_id, state = store.get_or_create("")
    assert session_id.startswith("s-")
    assert state.session_id == session_id
