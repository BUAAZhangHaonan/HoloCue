"""Real HTTP routing and SQLite tests; these tests issue no model generations."""

import pytest
from fastapi.testclient import TestClient

from holocue.api import create_app
from holocue.config import list_scenes, load_scene, scene_fingerprint
from holocue.provider import OpenAICompatiblePlanner
from holocue.service import Service
from holocue.store import Store


@pytest.mark.parametrize("scene_id", [s["scene_id"] for s in list_scenes()])
def test_session_creation_and_atomic_snapshot(scene_id, tmp_path):
    service = Service(Store(tmp_path / "state.sqlite"), OpenAICompatiblePlanner())
    with TestClient(create_app(service)) as client:
        response = client.post("/api/v1/sessions", json={"scene_id": scene_id})
        assert response.status_code == 201
        state = response.json()
        assert state["scene_fingerprint"] == scene_fingerprint(load_scene(scene_id))
        snapshot = client.get(f"/api/v1/sessions/{state['session_id']}/snapshot")
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert body["state"]["revision"] == body["display"]["revision"]
        assert len(body["display"]["object_poses"]) == len(load_scene(scene_id).objects)
        assert client.get("/api/v1/scenes").status_code == 200
        assert client.get("/api/v1/scenes/no_such_scene").status_code == 404
        stale = client.post(
            f"/api/v1/sessions/{state['session_id']}/control/pause", json={"expected_revision": 20}
        )
        assert stale.status_code == 409


def test_unknown_session_is_404(tmp_path):
    service = Service(Store(tmp_path / "state.sqlite"), OpenAICompatiblePlanner())
    with TestClient(create_app(service)) as client:
        assert client.get("/api/v1/sessions/unknown").status_code == 404
        assert client.get("/api/v1/sessions/unknown/snapshot").status_code == 404
