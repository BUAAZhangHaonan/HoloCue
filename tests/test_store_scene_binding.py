"""Exercise database version isolation with real SQLite and offline API lifespans."""

import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from holocue.api import create_app
from holocue.models import UserMessage
from holocue.service import Service
from holocue.state import DomainError
from holocue.store import Store


def database_dump(path):
    with sqlite3.connect(path) as connection:
        return list(connection.iterdump())


def planning_session(store, selected):
    initial = store.create("blocks", "live", selected_set=selected)
    job, state, _ = store.begin(
        initial.session_id,
        UserMessage(text="保持任务", request_id="planning-check", expected_revision=0),
    )
    return job, state


def application(path):
    return create_app(Service(Store(path), SimpleNamespace(mode="live")))


def assert_startup_rejected_without_changes(path, match="scene set"):
    before = database_dump(path)
    with pytest.raises(DomainError, match=match):
        with TestClient(application(path)):
            pytest.fail("A mismatched state database must not start serving routes")
    assert database_dump(path) == before


@pytest.mark.parametrize("original", ["legacy", "reconstructed"])
@pytest.mark.parametrize("bound", [False, True])
def test_wrong_api_version_does_not_recover_or_rewrite_original_database(
    monkeypatch, tmp_path, original, bound
):
    path = tmp_path / "state.sqlite"
    store = Store(path)
    if bound:
        store.recover(original)
    job, before_state = planning_session(store, original)
    before_job = store.job(job["id"])
    before_events = store.events(before_state.session_id)
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "legacy" if original == "reconstructed" else "reconstructed")
    assert_startup_rejected_without_changes(path)
    assert store.get(before_state.session_id) == before_state
    assert store.get(before_state.session_id).execution == "planning"
    assert store.job(job["id"]) == before_job
    assert store.job(job["id"])["status"] == "planning"
    assert store.events(before_state.session_id) == before_events


@pytest.mark.parametrize("selected", ["legacy", "reconstructed"])
def test_empty_database_binds_and_same_version_recovers_normally(monkeypatch, tmp_path, selected):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", selected)
    path = tmp_path / "state.sqlite"
    app = application(path)
    with TestClient(app) as client:
        assert client.get("/health").json()["scene_set"] == selected
        with sqlite3.connect(path) as connection:
            assert connection.execute(
                "SELECT value FROM store_metadata WHERE key='scene_set'"
            ).fetchone() == (selected,)
        job, before = planning_session(app.state.service.store, selected)
    with TestClient(application(path)) as client:
        state = client.get(f"/api/v1/sessions/{before.session_id}")
        assert state.status_code == 200
        after = state.json()
        assert after["scene_set"] == selected
        assert after["execution"] == "paused"
        assert after["revision"] == before.revision + 1
        assert after["epoch"] == before.epoch + 1
        assert after["history"] == before.history
        assert after["queue"] == before.model_dump(mode="json")["queue"]
        assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "interrupted"
        assert client.get(f"/api/v1/sessions/{before.session_id}/events").status_code == 200


@pytest.mark.parametrize("selected", ["legacy", "reconstructed"])
def test_existing_explicit_same_version_database_can_bind_without_rewriting_history(
    monkeypatch, tmp_path, selected
):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", selected)
    path = tmp_path / "state.sqlite"
    store = Store(path)
    job, before = planning_session(store, selected)
    with TestClient(application(path)) as client:
        state = client.get(f"/api/v1/sessions/{before.session_id}").json()
        assert state["execution"] == "paused"
        assert state["history"] == before.history
        assert state["scene_set"] == selected
        assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "interrupted"


@pytest.mark.parametrize("selected", ["legacy", "reconstructed"])
def test_mixed_database_checks_all_sessions_before_recovery(monkeypatch, tmp_path, selected):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", selected)
    path = tmp_path / "state.sqlite"
    store = Store(path)
    planning_session(store, selected)
    planning_session(store, "legacy" if selected == "reconstructed" else "reconstructed")
    assert_startup_rejected_without_changes(path)


def test_empty_database_binding_cannot_be_reassigned(monkeypatch, tmp_path):
    path = tmp_path / "state.sqlite"
    Store(path).recover("legacy")
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    assert_startup_rejected_without_changes(path)


def test_nonempty_database_missing_explicit_scene_set_is_not_inferred(monkeypatch, tmp_path):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    path = tmp_path / "state.sqlite"
    store = Store(path)
    _, state = planning_session(store, "reconstructed")
    data = state.model_dump(mode="json")
    del data["scene_set"]
    with store.connection() as connection:
        connection.execute("UPDATE sessions SET data=? WHERE id=?", (json.dumps(data), state.session_id))
    assert_startup_rejected_without_changes(path)


def test_orphan_records_do_not_count_as_an_empty_database(monkeypatch, tmp_path):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    path = tmp_path / "state.sqlite"
    store = Store(path)
    planning_session(store, "legacy")
    with store.connection() as connection:
        connection.execute("DELETE FROM sessions")
    assert_startup_rejected_without_changes(path, match="versioned session")


def test_bound_database_rejects_cross_set_store_writes(tmp_path):
    path = tmp_path / "state.sqlite"
    old_handle = Store(path)
    Store(path).recover("legacy")
    before = database_dump(path)
    with pytest.raises(DomainError, match="another scene set"):
        old_handle.create("blocks", "live", selected_set="reconstructed")
    assert database_dump(path) == before


def test_state_job_and_events_reject_foreign_records_after_startup(monkeypatch, tmp_path):
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    foreign = Store(tmp_path / "foreign.sqlite")
    job, state = planning_session(foreign, "legacy")
    path = tmp_path / "state.sqlite"
    app = application(path)
    with TestClient(app) as client:
        # Direct SQL represents externally introduced inconsistent data, not a supported writer.
        with foreign.connection() as source, app.state.service.store.connection() as target:
            for table in ("sessions", "jobs", "events"):
                for row in source.execute(f"SELECT * FROM {table}"):
                    placeholders = ",".join("?" for _ in row)
                    target.execute(f"INSERT INTO {table} VALUES({placeholders})", tuple(row))
        before = database_dump(path)
        for route in (
            f"/api/v1/sessions/{state.session_id}",
            f"/api/v1/jobs/{job['id']}",
            f"/api/v1/sessions/{state.session_id}/events",
            f"/api/v1/sessions/{state.session_id}/snapshot",
        ):
            response = client.get(route)
            assert response.status_code == 422
            assert "another scene set" in response.json()["detail"]
        assert database_dump(path) == before
