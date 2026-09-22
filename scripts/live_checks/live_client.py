"""Shared HTTP scaffolding for the live acceptance scripts.

Covers the API plumbing every live check repeats: optional bearer auth,
revision-guarded message submission, job polling to a terminal status,
control endpoints and session/display reads. The scenario scripts
(smoke / interrupt / extended / engine_round) stay thin layers on top;
their CLI and output JSON structures are unchanged.

Import pattern (same convention as the scene kits):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from live_client import make_client, send, ...
"""

import os, time, uuid
import httpx


def make_client(api: str, timeout: float = 10.0) -> httpx.Client:
    headers = (
        {"Authorization": "Bearer " + os.environ["HOLOCUE_API_KEY"]} if os.getenv("HOLOCUE_API_KEY") else {}
    )
    return httpx.Client(base_url=api, headers=headers, timeout=timeout)


def req(client, method, path, **kw):
    r = client.request(method, path, **kw)
    r.raise_for_status()
    return r.json()


def state(client, sid):
    return req(client, "GET", f"/api/v1/sessions/{sid}")


def display(client, sid):
    return req(client, "GET", f"/api/v1/sessions/{sid}/display")


def new_session(client, scene: str) -> str:
    return req(client, "POST", "/api/v1/sessions", json={"scene_id": scene})["session_id"]


def send(client, sid, text, timeout=100.0, poll=0.3):
    """Revision-guarded submit, then poll the job out of 'planning'.

    Returns (job, session_state, elapsed_s). A terminal non-done status is
    returned as-is so callers record the model's real outcome.
    """
    s = state(client, sid)
    t0 = time.perf_counter()
    j = req(
        client,
        "POST",
        f"/api/v1/sessions/{sid}/messages",
        json={"text": text, "request_id": uuid.uuid4().hex, "expected_revision": s["revision"]},
    )
    while j["status"] == "planning":
        if time.perf_counter() - t0 > timeout:
            raise TimeoutError("planner timeout")
        time.sleep(poll)
        j = req(client, "GET", "/api/v1/jobs/" + j["id"])
    return j, state(client, sid), time.perf_counter() - t0


def control(client, sid, operation):
    s = state(client, sid)
    return req(
        client,
        "POST",
        f"/api/v1/sessions/{sid}/control/{operation}",
        json={"expected_revision": s["revision"]},
    )
