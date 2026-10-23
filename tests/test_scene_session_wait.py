"""Real browser DOM timing checks; no application service, model or scene task runs."""

import json
import time

import pytest
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from scripts.tests import audit_viewer_live as audit


SCENE = {"scene_id": "shelf_picking", "title": "货架拣选与包裹核验"}
STATE = {
    "session_id": "new-session",
    "scene_id": "shelf_picking",
    "scene_set": "reconstructed",
    "revision": 0,
    "epoch": 0,
    "backend_mode": "live",
}


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def context(browser, tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(audit, "scene_set", lambda: "reconstructed")
    monkeypatch.setattr(audit, "list_scenes", lambda: [SCENE])
    page = browser.new_page()
    page.set_content(
        '<div><p>场景</p><input role="combobox" value="旧场景" id="scene"></div>'
        '<div><p>会话标识</p><input value="old-session" id="session"></div>'
    )
    view = tmp_path / "viewer/client_7_view.json"
    view.parent.mkdir()
    calls = []

    def read(sid, timeout):
        calls.append((sid, timeout))
        view.write_text(json.dumps(dict(STATE, generated_at=time.time())))
        return dict(STATE)

    yield page, view, calls, read
    page.close()


def ready(page):
    page.evaluate(
        "([title,sid]) => {scene.value=title;session.value=sid}", [SCENE["title"], STATE["session_id"]]
    )


def receipt(directory):
    return json.loads((directory / "scene_selection.jsonl").read_text().splitlines()[-1])


def test_browser_wait_reads_title_and_fresh_session_atomically(context, tmp_path):
    page, view, calls, read = context
    # The title changes first; the old SID must never be read through the API.
    # A busy browser interval then ends with the corresponding new SID.
    page.evaluate(
        """(title) => {
        scene.value=title;
        setTimeout(() => {
            const until=performance.now()+150;
            while(performance.now()<until) {}
            session.value='new-session';
        }, 20);
    }""",
        SCENE["title"],
    )
    result = audit.wait_scene_session(
        page,
        read,
        tmp_path,
        expected_scene=SCENE,
        previous_session_id="old-session",
        client_view_path=view,
        timeout=2,
    )
    assert result["session_id"] == "new-session"
    assert len(calls) == 1 and calls[0][0] == "new-session" and 0 < calls[0][1] <= 2
    trace = receipt(tmp_path)
    assert trace["status"] == "passed" and trace["elapsed_s"] < 2
    assert trace["browser_read_completed_at"] <= trace["api_read_started_at"]
    assert trace["client_view_generated_at"] >= trace["started_at"]
    assert trace["last_client_records"][0]["path"] == str(view)


def test_changed_scene_with_old_sid_times_out_without_api_read(context, tmp_path):
    page, view, calls, read = context
    page.evaluate("title => scene.value=title", SCENE["title"])
    with pytest.raises(PlaywrightTimeoutError, match="Timeout"):
        audit.wait_scene_session(
            page,
            read,
            tmp_path,
            expected_scene=SCENE,
            previous_session_id="old-session",
            client_view_path=view,
            timeout=0.25,
        )
    assert calls == []
    assert receipt(tmp_path)["status"] == "failed"


def test_initial_scene_can_keep_its_existing_sid(context, tmp_path):
    page, view, calls, read = context
    ready(page)
    result = audit.wait_scene_session(page, read, tmp_path, timeout=2)
    assert result["session_id"] == STATE["session_id"]
    assert result["client_view_path"] == view


@pytest.mark.parametrize("field,value", [("scene_id", "server_rack"), ("scene_set", "legacy")])
def test_atomic_ui_does_not_accept_wrong_api_scene_or_set(context, tmp_path, field, value):
    page, view, calls, read = context
    ready(page)
    with pytest.raises(AssertionError, match="API scene/version"):
        audit.wait_scene_session(
            page,
            lambda sid, timeout: dict(read(sid, timeout), **{field: value}),
            tmp_path,
            expected_scene=SCENE,
            timeout=2,
        )
    assert receipt(tmp_path)["status"] == "failed"


@pytest.mark.parametrize("stale", [False, True])
def test_only_fresh_matching_bound_client_record_is_accepted(context, tmp_path, stale):
    page, view, calls, read = context
    ready(page)
    old_record = dict(STATE, generated_at=time.time() - 10)
    if not stale:
        old_record["session_id"] = "old-session"
    view.write_text(json.dumps(old_record))
    other = view.with_name("client_8_view.json")

    def wrong_client(sid, timeout):
        other.write_text(json.dumps(dict(STATE, generated_at=time.time())))
        return dict(STATE)

    with pytest.raises(TimeoutError, match="wait budget"):
        audit.wait_scene_session(
            page, wrong_client, tmp_path, expected_scene=SCENE, client_view_path=view, timeout=0.3
        )
    assert receipt(tmp_path)["last_client_records"][0]["generated_at"] == old_record["generated_at"]


def test_slow_api_reply_cannot_be_accepted_after_total_budget(context, tmp_path):
    page, view, calls, read = context
    ready(page)

    def slow(sid, timeout):
        time.sleep(timeout + 0.03)
        return read(sid, timeout)

    with pytest.raises(TimeoutError, match="wait budget"):
        audit.wait_scene_session(page, slow, tmp_path, expected_scene=SCENE, timeout=0.3)
    trace = receipt(tmp_path)
    assert trace["status"] == "failed" and trace["elapsed_s"] > trace["timeout_s"]


def test_switch_to_same_scene_does_not_require_a_new_sid(context, tmp_path):
    page, view, calls, read = context
    ready(page)
    result = audit.wait_scene_session(
        page, read, tmp_path, expected_scene=SCENE, previous_session_id=None, client_view_path=view, timeout=2
    )
    assert result["session_id"] == STATE["session_id"] and len(calls) == 1
