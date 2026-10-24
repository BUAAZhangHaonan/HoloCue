"""Run at most two authored workflows with real Viser RGB and a hardware client.

Uses GUI controls for every mutation, read-only API evidence, and the viewer's
monotonic action clock. Blender and browser/DOM screenshots are not involved.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

import httpx
import numpy as np
from playwright.sync_api import sync_playwright

from holocue.config import list_scenes, load_scene, root, runtime_dir
from holocue.models import DisplayCue, Pose
from holocue.spatial import matrix, trajectory
from scripts.tests.live_twelve_scenes import signature, require_persistent_visible


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def ui_input(page, label):
    return page.get_by_text(label, exact=True).locator("xpath=ancestor::*[.//input][1]").locator("input")


class CameraRun:
    def __init__(self, page, api, directory, spec):
        self.page, self.api, self.directory, self.spec = page, api, directory, spec
        self.sid = None
        self.started = None
        self.trace = directory / "timeline.jsonl"
        self.snapshots = []
        self.last_view = None

    def note(self, kind, **data):
        with self.trace.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": time.time(), "kind": kind, **data}, ensure_ascii=False) + "\n")

    def get(self, suffix=""):
        r = self.api.get(f"/api/v1/sessions/{self.sid}{suffix}")
        r.raise_for_status()
        return r.json()

    def preserve_failure(self):
        if not self.sid:
            return
        try:
            events = self.get("/events")
            save(self.directory / "events.json", events)
            save(self.directory / "failure_snapshot.json", self.get("/snapshot"))
            save(self.directory / "snapshots.json", self.snapshots)
            jobs = []
            for event in events:
                if event["kind"] == "turn_started":
                    response = self.api.get("/api/v1/jobs/" + event["data"]["job_id"])
                    response.raise_for_status()
                    jobs.append(response.json())
            save(self.directory / "jobs.json", jobs)
        except Exception:
            save(self.directory / "evidence_collection_error.json", {"traceback": traceback.format_exc()})

    def view(self):
        matches = []
        for path in (runtime_dir() / "viewer").glob("client_*_view.json"):
            value = json.loads(path.read_text())
            if value.get("session_id") == self.sid and time.time() - value["generated_at"] < 3:
                matches.append(value)
        if len(matches) != 1:
            return None
        v = matches[0]
        if v != self.last_view:
            self.note("view", **v)
            self.last_view = v
        return v

    def wait(self, predicate, description, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.started and time.perf_counter() - self.started > 180:
                raise TimeoutError("Workflow exceeded the 180 second runtime budget")
            value = predicate()
            if value:
                return value
            self.page.wait_for_timeout(80)
        raise TimeoutError(description)

    def settled(self, state):
        v = self.view()
        return (
            v
            if v
            and v["revision"] == state["revision"]
            and v["epoch"] == state["epoch"]
            and v["pending_commands"] == 0
            and not v["camera_capture_active"]
            and v["camera_ready"]
            else None
        )

    def control(self, label, expected_execution=None):
        old = self.get()
        self.page.get_by_role("tab", name="任务", exact=True).click()
        self.note("control_click", label=label, revision=old["revision"])
        self.page.get_by_role("button", name=label, exact=True).click()
        state = self.wait(
            lambda: (
                s
                if (s := self.get())["revision"] > old["revision"]
                and (expected_execution is None or s["execution"] == expected_execution)
                else None
            ),
            label,
        )
        self.wait(lambda: self.settled(state), "Viewer did not accept control")
        return state

    def message(self, text):
        self.page.get_by_role("tab", name="任务", exact=True).click()
        ui_input(self.page, "任务指令").fill(text)
        ui_input(self.page, "任务指令").press("Tab")
        old = self.get()
        if self.started is None:
            self.started = time.perf_counter()
            self.note("runtime_started", timing_scope="before first send click, includes camera capture")
        self.note("send_click", revision=old["revision"], text=text)
        self.page.get_by_role("button", name="发送任务", exact=True).click()
        state = self.wait(
            lambda: (
                s
                if (s := self.get())["revision"] > old["revision"] + 1 and s["execution"] != "planning"
                else None
            ),
            "Model did not commit",
        )
        self.wait(lambda: self.settled(state), "Viewer did not accept model plan")
        return state

    def camera(self, label):
        folder = runtime_dir() / "viewer" / "observations" / self.sid
        before = set(folder.glob("view_*.json"))
        self.page.get_by_role("tab", name="观察", exact=True).click()
        self.page.get_by_role("button", name="采集相机图像", exact=True).click()
        path = self.wait(
            lambda: next(iter(set(folder.glob("view_*.json")) - before), None), "Camera export failed", 25
        )
        metadata = json.loads(path.read_text())
        self.note("camera_export", label=label, metadata=metadata)
        self.wait(lambda: self.settled(self.get()), "Camera did not release")
        self.page.get_by_role("tab", name="任务", exact=True).click()
        return metadata

    def endpoint(self, state, label, persistent=True):
        snap = self.get("/snapshot")
        if persistent:
            require_persistent_visible(snap, self.spec.task_contract.persistent_targets)
        cue = DisplayCue.model_validate(snap["display"]["cues"][0])
        tid = state["queue"][0]["task_id"]
        self.wait(
            lambda: (
                v
                if (v := self.view())
                and v["revision"] == state["revision"]
                and v["elapsed_s"].get(tid, 0) >= cue.interaction.duration_s
                else None
            ),
            "Action did not reach its endpoint",
            30,
        )
        self.camera(label)
        self.snapshots.append({"label": label, "snapshot": self.get("/snapshot"), "view": self.view()})
        completed = self.control("确认完成")
        confirmed = self.get("/snapshot")
        pose = Pose.model_validate(confirmed["display"]["object_poses"][cue.target_id])
        if not np.allclose(matrix(pose), matrix(trajectory(cue, cue.interaction.duration_s)), atol=1e-7):
            raise AssertionError("Explicit completion did not persist the exact endpoint pose")
        self.snapshots.append({"label": label + "_confirmed", "snapshot": confirmed, "view": self.view()})
        return completed

    def run(self):
        setup = time.perf_counter()
        self.page.get_by_role("tab", name="任务", exact=True).click()
        previous = ui_input(self.page, "会话标识").input_value().strip()
        choice = self.page.get_by_role("combobox", name="场景", exact=True)
        # Every scene is a new session. The first page starts on the first batch scene.
        if choice.input_value() != self.spec.title:
            choice.click()
            self.page.get_by_role("option", name=self.spec.title, exact=True).click()
            self.wait(
                lambda: (
                    s
                    if (s := ui_input(self.page, "会话标识").input_value().strip()) and s != previous
                    else None
                ),
                "New scene session not published",
                90,
            )
        self.sid = self.wait(lambda: ui_input(self.page, "会话标识").input_value().strip(), "No session ID")
        state = self.get()
        if state["scene_id"] != self.spec.scene_id or state["queue"] or state["history"]:
            raise AssertionError("Expected a fresh selected scene session")
        ready = self.wait(lambda: self.settled(state), "Scene camera not ready", 90)
        if ready["playback_speed"] != 1 or ready["observation_mode"] != "camera_rgb":
            raise AssertionError("Runtime requires 1x playback and actual camera RGB")
        render_settings = self.page.evaluate("""() => {
            const canvas = window.__viserMutable.canvas;
            return {fixed_dpr:window.__viserTestpoints.devSettings.get().fixedDpr,
                    window_dpr:window.devicePixelRatio, url:location.href,
                    width:canvas.width,height:canvas.height,
                    css_width:canvas.clientWidth,css_height:canvas.clientHeight};
        }""")
        if (
            render_settings["fixed_dpr"] != 1
            or render_settings["width"] != render_settings["css_width"]
            or render_settings["height"] != render_settings["css_height"]
        ):
            raise AssertionError("Runtime measurement requires an actual fixed render DPR of 1")
        self.note("render_settings", **render_settings)
        setup_seconds = time.perf_counter() - setup
        self.page.evaluate((root() / "scripts/tests/runtime_camera_recording.js").read_text())
        recorder = self.page.evaluate(
            "() => window.__holocueRuntimeCameraRecording.start({maxFps:15,videoBitsPerSecond:4000000,readyTimeoutMs:10000,mimeType:'video/webm;codecs=vp8'})"
        )
        self.note("recorder_started", receipt=recorder)
        try:
            state = self.message(self.spec.initial_instruction)
            expected = [
                (s.target_id, s.action, s.reference_id, s.angle_deg)
                for s in self.spec.task_contract.ordered_steps
            ]
            if [
                signature(t) for t in state["queue"] if t["semantic"]["task_role"] != "background"
            ] != expected:
                raise AssertionError("Live RGB plan differs from the authored contract")
            background = {
                t["semantic"]["target_id"]
                for t in state["queue"]
                if t["semantic"]["task_role"] == "background"
            }
            if background != set(self.spec.task_contract.persistent_targets):
                raise AssertionError("Persistent background targets differ")
            original = state["queue"]
            first_id = original[0]["task_id"]
            duration = self.get("/snapshot")["display"]["cues"][0]["interaction"]["duration_s"]
            self.wait(
                lambda: v if (v := self.view()) and v["elapsed_s"].get(first_id, 0) >= 0.5 else None,
                "Initial action never moved",
            )
            state = self.control("暂停动作", "paused")
            pause_view = self.view()
            paused_elapsed = pause_view["elapsed_s"][first_id]
            if not 0 < paused_elapsed < duration:
                raise AssertionError("Pause missed the moving interval; no clock rewind is allowed")
            self.camera("paused_main")
            state = self.message(self.spec.task_contract.interrupt_instruction)
            if not state["suspended"] or state["suspended"][-1] != original:
                raise AssertionError("Interrupt changed suspended task identities or parameters")
            if len(state["queue"]) != 1 or signature(state["queue"][0]) != (
                self.spec.task_contract.interrupt_target,
                "inspect_back",
                None,
                None,
            ):
                raise AssertionError("Unexpected temporary task")
            state = self.endpoint(state, "temporary_endpoint", persistent=False)
            if state["queue"] or state["execution"] != "idle" or state["suspended"][-1] != original:
                raise AssertionError("Temporary completion did not retain the original plan")
            suspended_elapsed = self.view()["elapsed_s"][first_id]
            if abs(suspended_elapsed - paused_elapsed) > 1e-7:
                raise AssertionError("Suspended action clock advanced")
            state = self.control("恢复任务", "running")
            if state["queue"] != original or state["suspended"]:
                raise AssertionError("Resume changed the original plan")
            accepted = []
            for path in (runtime_dir() / "viewer").glob("client_*.jsonl"):
                accepted.extend(json.loads(line) for line in path.read_text().splitlines())
            resumed = [
                row
                for row in accepted
                if row.get("session_id") == self.sid
                and row["kind"] == "snapshot"
                and row.get("revision") == state["revision"]
            ]
            if len(resumed) != 1 or abs(resumed[0]["elapsed_s"][first_id] - paused_elapsed) > 1e-7:
                raise AssertionError("Resume did not preserve the exact suspended action clock")
            self.note("resume_clock_verified", accepted_snapshot=resumed[0], paused_elapsed=paused_elapsed)
            for i, expected_task in enumerate(expected):
                if signature(state["queue"][0]) != expected_task:
                    raise AssertionError("Main task order changed")
                state = self.endpoint(state, f"main_{i + 1}_endpoint")
            if state["queue"] or state["suspended"] or state["execution"] != "idle":
                raise AssertionError("Workflow not fully completed")
            seconds = time.perf_counter() - self.started
            self.note("runtime_completed", seconds=seconds)
            self.started = None
            self.camera("final")
            events = self.get("/events")
            save(self.directory / "events.json", events)
            save(self.directory / "final.json", state)
            save(self.directory / "snapshots.json", self.snapshots)
            job_records = []
            for event in events:
                if event["kind"] == "turn_started":
                    response = self.api.get("/api/v1/jobs/" + event["data"]["job_id"])
                    response.raise_for_status()
                    job_records.append(response.json())
            save(self.directory / "jobs.json", job_records)
            if any(j["status"] != "done" for j in job_records):
                raise AssertionError("A model job did not complete")
            jobs = [j["data"] for j in job_records]
            if len(jobs) != 2:
                raise AssertionError("Expected exactly two live multimodal calls")
            image_receipts = []
            for record, job in zip(job_records, jobs):
                body = job["request_body"]
                required = {
                    "model": "Qwen/Qwen3.5-4B",
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "max_tokens": 1600,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
                if any(body.get(key) != value for key, value in required.items()):
                    raise AssertionError("Model or sampling parameters changed")
                images = [
                    part["image_url"]["url"]
                    for message in body["messages"]
                    if isinstance(message["content"], list)
                    for part in message["content"]
                    if part["type"] == "image_url"
                ]
                if len(images) != 1 or not images[0].startswith("data:image/png;base64,"):
                    raise AssertionError("Each model request must contain one real camera PNG")
                digest = hashlib.sha256(base64.b64decode(images[0].split(",", 1)[1])).hexdigest()
                matches = []
                for path in (runtime_dir() / "viewer/observations" / self.sid).glob("*.json"):
                    meta = json.loads(path.read_text())
                    if meta["purpose"] == "model_input" and meta["request_id"] == record["request_id"]:
                        if (
                            meta["image_sha256"] != digest
                            or hashlib.sha256(path.with_suffix(".png").read_bytes()).hexdigest() != digest
                        ):
                            raise AssertionError("Saved camera PNG differs from the actual request bytes")
                        if (meta["session_id"], meta["scene_id"], meta["revision"], meta["epoch"]) != (
                            self.sid,
                            self.spec.scene_id,
                            job["revision"] - 2,
                            record["epoch"] - 1,
                        ):
                            raise AssertionError("Camera state version is not the submitted request version")
                        matches.append(meta)
                if len(matches) != 1:
                    raise AssertionError("Model image is not bound to exactly one camera capture")
                image_receipts.extend(matches)
                wire = json.loads(job["raw_http_body"])["choices"][0]["message"]["content"]
                if wire != job["raw_response"] or json.loads(wire) != job["decision"]:
                    raise AssertionError("Committed model decision differs from raw HTTP output")
            return {
                "scene_id": self.spec.scene_id,
                "session_id": self.sid,
                "passed": seconds <= 180,
                "runtime_seconds": seconds,
                "scene_setup_seconds": setup_seconds,
                "main_steps": len(expected),
                "temporary_steps": 1,
                "model_calls": 2,
                "model_seconds": sum(j["latency_s"] for j in jobs),
                "model_input_images": image_receipts,
                "playback_speed": 1,
                "render_settings": render_settings,
                "protocol": "runtime_camera_v1",
            }
        finally:
            prior_error = sys.exc_info()[0] is not None
            try:
                recording = self.page.evaluate("() => window.__holocueRuntimeCameraRecording.stop()")
                encoded = recording.pop("base64", None)
                if encoded:
                    (self.directory / "video.webm").write_bytes(base64.b64decode(encoded))
                save(self.directory / "video.json", recording)
                if not recording["ok"]:
                    raise AssertionError(f"Recording failed: {recording['errors']}")
            except Exception:
                save(self.directory / "recording_error.json", {"traceback": traceback.format_exc()})
                if not prior_error:
                    raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", nargs="+", required=True, choices=[s["scene_id"] for s in list_scenes()])
    parser.add_argument("--cdp", default="http://127.0.0.1:19222")
    parser.add_argument("--viewer", default="http://127.0.0.1:18780/?fixedDpr=1")
    parser.add_argument("--api", default="http://127.0.0.1:8750")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= len(args.scenes) <= 2 or len(set(args.scenes)) != len(args.scenes):
        parser.error("Each batch must contain one or two distinct scenes")
    if not args.out.resolve().is_relative_to(root()):
        parser.error("Output must remain within the project")
    args.out.mkdir(parents=True, exist_ok=False)
    headers = (
        {"Authorization": "Bearer " + os.environ["HOLOCUE_API_KEY"]}
        if os.environ.get("HOLOCUE_API_KEY")
        else {}
    )
    results = []
    with httpx.Client(base_url=args.api, timeout=10, headers=headers) as api, sync_playwright() as p:
        health = api.get("/health").json()
        if health["backend_mode"] != "live" or health["scene_set"] != "reconstructed":
            raise AssertionError("Expected reconstructed scenes with live model")
        client_start_wall, client_start = time.time(), time.perf_counter()
        browser = p.chromium.connect_over_cdp(args.cdp)
        page = browser.contexts[0].pages[0]
        page.set_default_timeout(15000)
        if not page.url.startswith(args.viewer):
            page.goto(args.viewer, wait_until="domcontentloaded", timeout=30000)
        page.get_by_role("tab", name="任务", exact=True).wait_for(timeout=90000)
        page.get_by_role("combobox", name="场景", exact=True).wait_for(timeout=90000)
        save(
            args.out / "client_initialization.json",
            {
                "started_at": client_start_wall,
                "completed_at": time.time(),
                "seconds": time.perf_counter() - client_start,
                "scope": "CDP connection, optional navigation, UI mount; model/API/Viser services were already started and have separate process receipts",
                "cdp": args.cdp,
                "viewer": args.viewer,
            },
        )
        for sid in args.scenes:
            directory = args.out / sid
            directory.mkdir()
            run = CameraRun(page, api, directory, load_scene(sid))
            try:
                result = run.run()
                save(directory / "result.json", result)
                results.append(result)
                print(
                    json.dumps(
                        {k: v for k, v in result.items() if k != "model_input_images"}, ensure_ascii=False
                    ),
                    flush=True,
                )
            except Exception:
                save(directory / "failure.json", {"traceback": traceback.format_exc(), "time": time.time()})
                run.preserve_failure()
                raise
            finally:
                save(args.out / "report.json", results)


if __name__ == "__main__":
    main()
