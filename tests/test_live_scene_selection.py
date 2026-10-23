"""CLI/report regression only; these fixtures are not model or E2E evidence."""

import json
import sys

import pytest
import httpx

from scripts.tests import live_twelve_scenes as live


class BeforeNetwork(RuntimeError):
    pass


@pytest.mark.parametrize("mismatch_at", ["health", "session", "state"])
def test_actual_entry_rejects_a_different_server_scene_set(monkeypatch, tmp_path, mismatch_at):
    """HTTP transport fixtures reject version mixing before a planning request."""
    requested = []
    client_type = httpx.Client

    def response(request):
        requested.append((request.method, request.url.path))
        stage = {"/health": "health", "/api/v1/sessions": "session"}.get(request.url.path, "state")
        return httpx.Response(
            200,
            json={
                "backend_mode": "live",
                "scene_set": "legacy" if stage == mismatch_at else "reconstructed",
                "session_id": "unit-test-only",
            },
        )

    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    monkeypatch.setattr(
        sys, "argv", ["live_twelve_scenes.py", "--scenes", "connector", "--out", str(tmp_path)]
    )
    monkeypatch.setattr(
        live.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(response), **kwargs)
    )
    with pytest.raises(ValueError, match="API scene_set 'legacy' differs from 'reconstructed'"):
        live.main()
    assert not any(path.endswith("/messages") for _, path in requested)
    assert not json.loads((tmp_path / "selection.json").read_text())["complete"]


def selection_before_network(monkeypatch, tmp_path, scene_ids):
    """Use the actual main entry and stop before opening any HTTP client."""
    output = tmp_path / "live"
    argv = ["live_twelve_scenes.py", "--out", str(output)]
    if scene_ids is not None:
        argv.extend(["--scenes", *scene_ids])
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    monkeypatch.setattr(sys, "argv", argv)

    def stop(**kwargs):
        raise BeforeNetwork

    monkeypatch.setattr(live.httpx, "Client", stop)
    with pytest.raises(BeforeNetwork):
        live.main()
    assert json.loads((output / "report.json").read_text()) == []
    return output, json.loads((output / "selection.json").read_text())


@pytest.mark.parametrize(
    "scene_ids,message",
    [
        (["unknown_scene"], "invalid choice"),
        (["connector", "connector"], "duplicate scene IDs"),
        ([], "expected at least one argument"),
    ],
)
def test_invalid_cli_selection_is_rejected_before_output_or_http(
    monkeypatch, tmp_path, capsys, scene_ids, message
):
    output = tmp_path / "rejected"
    monkeypatch.setenv("HOLOCUE_SCENE_SET", "reconstructed")
    monkeypatch.setattr(sys, "argv", ["live_twelve_scenes.py", "--out", str(output), "--scenes", *scene_ids])

    def forbidden(**kwargs):
        pytest.fail("invalid selection reached the HTTP client")

    monkeypatch.setattr(live.httpx, "Client", forbidden)
    with pytest.raises(SystemExit) as error:
        live.main()
    assert error.value.code == 2
    assert message in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("scene_ids", [None, ["connector", "control_panel"]])
def test_real_main_records_default_or_explicit_contract_scope(monkeypatch, tmp_path, scene_ids):
    _, selection = selection_before_network(monkeypatch, tmp_path, scene_ids)
    assert selection["scene_set"] == "reconstructed"
    assert selection["requested_scene_ids"] == scene_ids
    assert selection["expected_scene_count"] == (12 if scene_ids is None else 2)
    assert selection["expected_step_count"] == (30 if scene_ids is None else 4)
    assert selection["all_available_scenes_selected"] is (scene_ids is None)
    if scene_ids is not None:
        assert selection["selected_scene_ids"] == scene_ids
    else:
        assert selection["selected_scene_ids"] == selection["available_scene_ids"]
    assert selection["completed_scene_count"] == 0
    assert not selection["complete"]


def test_default_cli_rejects_an_incomplete_scene_catalog(monkeypatch, tmp_path, capsys):
    output = tmp_path / "incomplete_catalog"
    monkeypatch.setattr(live, "list_scenes", lambda: [{"scene_id": "connector"}])
    monkeypatch.setattr(sys, "argv", ["live_twelve_scenes.py", "--out", str(output)])
    with pytest.raises(SystemExit) as error:
        live.main()
    assert error.value.code == 2
    assert "requires all twelve scenes" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("outcome", ["complete", "missing", "duplicate", "wrong_steps", "failed"])
def test_subset_report_requires_each_selected_contract(monkeypatch, tmp_path, outcome):
    output, selection = selection_before_network(monkeypatch, tmp_path, ["connector", "control_panel"])
    # Synthetic completion rows isolate report accounting; no workflow/model is mocked as accepted.
    rows = [
        {"scene_id": "connector", "steps": 2, "passed": True},
        {"scene_id": "control_panel", "steps": 2, "passed": True},
    ]
    if outcome == "missing":
        rows.pop()
    elif outcome == "duplicate":
        rows[1] = dict(rows[0])
    elif outcome == "wrong_steps":
        rows[1]["steps"] = 1
    elif outcome == "failed":
        rows[1]["passed"] = False
    progress = live.write_reports(output, selection, rows)
    assert progress["complete"] is (outcome == "complete")
    assert progress["expected_scene_count"] == 2
    assert progress["expected_step_count"] == 4
    assert not progress["all_available_scenes_selected"]
    assert json.loads((output / "report.json").read_text()) == rows
    assert json.loads((output / "selection.json").read_text()) == progress
