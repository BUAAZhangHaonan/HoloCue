"""Bounded real-browser isolation and recovery audit; faults affect one owned API only.

Run after sourcing .work/task_env.sh. --faults is deliberately opt-in and must run
after other API consumers finish. All successful model jobs retain their raw trace.
Fault-created API services are explicitly stopped before this audit exits. Start
the final API from outside this audit's resource guard after checking its report.
Stale display evidence is labelled a replay through the production VersionGate,
not a claim that a delayed HTTP packet was injected into the running viewer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit

import httpx
import psutil
from playwright.sync_api import sync_playwright

from holocue.config import load_scene, root
from holocue.versioning import VersionGate
from scripts.tests.live_twelve_scenes import LiveRun, signature


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def inside(path, base):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"Path must be inside {base}: {resolved}")
    return resolved


def preflight(args):
    project = root().resolve()
    for endpoint in (args.api, args.viewer):
        parsed = urlsplit(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Audit endpoints must be local HTTP services")
    for name in ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "PIP_CACHE_DIR", "PLAYWRIGHT_BROWSERS_PATH"):
        value = os.environ.get(name)
        if not value:
            raise ValueError(f"{name} must be set before running the audit")
        location = inside(value, project)
        if not (
            location.is_relative_to(project / ".work")
            or location.is_relative_to(project / "runs" / "simulation")
        ):
            raise ValueError(f"{name} must use .work or runs/simulation")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("CPU browser audit requires explicit empty CUDA_VISIBLE_DEVICES")
    args.out = inside(args.out, project / "runs" / "simulation")
    args.out.mkdir(parents=True, exist_ok=False)
    return project


class Audit:
    def __init__(self, args, http):
        self.args = args
        self.run = LiveRun(http, args.out)
        self.report = {
            "passed": False,
            "full_live_fault_coverage": False,
            "started_at": time.time(),
            "checks": {},
            "browser_errors": [],
            "faults_enabled": args.faults,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "limitations": [
                "Stale display rejection is a production VersionGate replay "
                "of real snapshots, not a live network injection."
            ],
        }
        self.pages = []
        self.contexts = []
        self.counter = 0
        self.fault_recovery_needed = False
        self.created_api_services = []
        self.send_timings = []

    def checkpoint(self, name, evidence):
        self.report["checks"][name] = evidence
        save(self.args.out / "report.json", self.report)

    def until(self, description, read, predicate, timeout=25):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = read()
            if predicate(last):
                return last
            time.sleep(0.12)
        raise TimeoutError(f"{description}; last observation: {last}")

    def state(self, sid):
        return self.run.state(sid)

    def view(self, sid, after=0, predicate=lambda data: True):
        def read():
            matches = []
            for path in (root() / "runs/simulation/viewer").glob("client_*_view.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["session_id"] == sid and data["generated_at"] > after:
                    data["evidence_file"] = str(path)
                    matches.append(data)
            return max(matches, key=lambda row: row["generated_at"]) if matches else None

        return self.until("fresh viewer export", read, lambda row: row is not None and predicate(row))

    @staticmethod
    def field(page, label):
        # Viser 1.1.1 labels do not associate their `for` with the input id.
        return page.get_by_text(label, exact=True).locator("xpath=ancestor::*[.//input][1]").locator("input")

    def tab(self, page, label):
        tab = page.get_by_role("tab", name=label, exact=True)
        if tab.get_attribute("aria-selected") != "true":
            tab.click()

    def click(self, page, name):
        self.tab(page, "任务")
        page.get_by_role("button", name=name, exact=True).click()

    def open_session(self, page, sid):
        self.tab(page, "任务")
        self.field(page, "会话标识").fill(sid)
        before = time.time()
        page.get_by_role("button", name="打开已有会话", exact=True).click()
        return self.view(sid, before)

    def send(self, page, sid, text):
        timing = {"session_id": sid, "text": text, "started_at": time.time(), "phases": []}
        self.send_timings.append(timing)

        def measure(name, action):
            start = time.time()
            monotonic_start = time.perf_counter()
            try:
                return action()
            finally:
                timing["phases"].append(
                    {
                        "name": name,
                        "started_at": start,
                        "finished_at": time.time(),
                        "elapsed_s": time.perf_counter() - monotonic_start,
                    }
                )
                save(self.args.out / "send_timings.json", self.send_timings)

        try:
            measure("tab", lambda: self.tab(page, "任务"))
            measure("fill", lambda: self.field(page, "任务指令").fill(text))
            before = measure("state_read", lambda: self.state(sid)["epoch"])
            measure("click", lambda: page.get_by_role("button", name="发送任务", exact=True).click())
            events = measure(
                "event_collection",
                lambda: self.until(
                    "new real model job",
                    lambda: self.run.request("GET", f"/api/v1/sessions/{sid}/events"),
                    lambda rows: any(
                        row["kind"] == "turn_started" and row["data"]["epoch"] > before for row in rows
                    ),
                ),
            )
            event = next(
                row
                for row in reversed(events)
                if row["kind"] == "turn_started" and row["data"]["epoch"] > before
            )
            timing["job_id"] = event["data"]["job_id"]
            timing["turn_started_at"] = event["timestamp"]
            return event["data"]["job_id"]
        finally:
            timing["finished_at"] = time.time()
            save(self.args.out / "send_timings.json", self.send_timings)

    def job(self, jid, expected="done"):
        job = self.until(
            "model job terminal state",
            lambda: self.run.request("GET", f"/api/v1/jobs/{jid}"),
            lambda row: row["status"] != "planning",
            self.args.model_timeout,
        )
        if job["status"] != expected:
            raise AssertionError(f"Expected {expected}, received {job}")
        if expected == "done" and (
            job["data"].get("backend_mode") != "live" or not job["data"].get("raw_response")
        ):
            raise AssertionError("Successful job lacks real model response evidence")
        return job

    def control(self, page, sid, button, execution):
        revision = self.state(sid)["revision"]
        self.click(page, button)
        return self.until(
            button,
            lambda: self.state(sid),
            lambda row: row["revision"] > revision and row["execution"] == execution,
        )

    def frozen(self, sid, duration=0.8):
        before = self.view(sid, time.time(), lambda row: not row["clock_advancing"])
        time.sleep(duration)
        after = self.view(sid, time.time(), lambda row: not row["clock_advancing"])
        if before["elapsed_s"] != after["elapsed_s"]:
            raise AssertionError("Stopped task clock continued advancing")
        return {"before": before, "after": after}

    def capture(self, page, name):
        page.screenshot(path=str(self.args.out / f"{name}.png"))

    def establish(self, browser):
        sessions = []
        for index, scene_id in enumerate(self.args.scenes):
            spec = load_scene(scene_id)
            initial = self.run.request("POST", "/api/v1/sessions", json={"scene_id": scene_id})
            sid = initial["session_id"]
            context = browser.new_context(
                viewport={"width": 1440 - index * 340, "height": 900},
                record_video_dir=str(self.args.out / f"client_{index}_video"),
            )
            self.contexts.append(context)
            context.tracing.start(screenshots=True, snapshots=True)
            page = context.new_page()
            self.pages.append(page)
            page.set_default_timeout(60000)
            page.on(
                "pageerror",
                lambda error, i=index: self.report["browser_errors"].append(
                    {"client": i, "error": str(error)}
                ),
            )
            page.goto(self.args.viewer, wait_until="networkidle", timeout=60000)
            page.get_by_role("tab", name="任务", exact=True).wait_for(timeout=60000)
            (self.args.out / f"client_{index}_initial_dom.yaml").write_text(
                page.locator("body").aria_snapshot(), encoding="utf-8"
            )
            self.open_session(page, sid)
            jid = self.send(page, sid, spec.initial_instruction)
            self.job(jid)
            state = self.control(page, sid, "暂停动作", "paused")
            actual = [
                signature(task) for task in state["queue"] if task["semantic"]["task_role"] != "background"
            ]
            expected = [
                (s.target_id, s.action, s.reference_id, s.angle_deg) for s in spec.task_contract.ordered_steps
            ]
            if actual != expected:
                raise AssertionError(f"{scene_id}: wrong real model ordered steps: {actual}")
            self.view(sid, time.time(), lambda row: row["revision"] == state["revision"])
            sessions.append((sid, spec))
            self.capture(page, f"client_{index}_initial")
            self.checkpoint(
                f"client_{index}_established",
                {"session_id": sid, "scene_id": scene_id, "real_model_job": jid, "state": state},
            )
        self.checkpoint(
            "two_independent_contexts",
            {"sessions": [item[0] for item in sessions], "scenes": self.args.scenes},
        )
        return sessions

    def isolation(self, sessions):
        evidence = []
        for index in (0, 1):
            page = self.pages[index]
            sid, _ = sessions[index]
            other, _ = sessions[1 - index]
            protected_state = self.state(other)
            protected_view = self.view(other, time.time())
            self.tab(page, "观察")
            checkbox = self.field(page, "跟随当前步骤")
            checkbox.uncheck()
            before = time.time()
            page.get_by_role("button", name="工作区域", exact=True).click()
            old = self.view(sid, before, lambda row: row["view_mode"] == "workspace")
            before = time.time()
            page.get_by_role("button", name="目标特写", exact=True).click()
            changed = self.view(sid, before, lambda row: row["view_mode"] == "detail")
            self.tab(page, "显示响应")
            focus = min(19.0, changed["focus_m"] + 0.35)
            self.field(page, "焦点数值 米").fill(str(focus))
            self.field(page, "焦点数值 米").press("Tab")
            changed = self.view(sid, time.time(), lambda row: abs(row["focus_m"] - focus) < 0.001)
            if changed["position_m"] == old["position_m"] and changed["look_at_m"] == old["look_at_m"]:
                raise AssertionError("Camera control did not change the operated client")
            self.control(page, sid, "恢复任务", "running")
            self.control(page, sid, "暂停动作", "paused")
            after_other = self.view(other, time.time())
            keys = (
                "session_id",
                "scene_id",
                "revision",
                "epoch",
                "position_m",
                "look_at_m",
                "focus_m",
                "view_mode",
                "elapsed_s",
            )
            if any(protected_view[key] != after_other[key] for key in keys):
                raise AssertionError("Other browser scene, camera, focus or task changed")
            if self.state(other) != protected_state:
                raise AssertionError("Other session API state changed")
            self.capture(page, f"client_{index}_isolated")
            evidence.append(
                {
                    "operated": sid,
                    "protected": other,
                    "changed_view": changed,
                    "protected_before": protected_view,
                    "protected_after": after_other,
                }
            )
        self.checkpoint("bidirectional_task_camera_focus_isolation", evidence)

    def invalidation(self, sid, spec):
        page = self.pages[0]
        old = self.run.request("GET", f"/api/v1/sessions/{sid}/snapshot")
        queue = self.state(sid)["queue"]
        jid = self.send(page, sid, spec.task_contract.interrupt_instruction)
        planning = self.state(sid)
        if planning["execution"] != "planning":
            raise AssertionError("Model completed before in-flight pause; scenario not exercised")
        paused = self.control(page, sid, "暂停动作", "paused")
        cancelled = self.job(jid, "superseded")
        if paused["queue"] != queue:
            raise AssertionError("In-flight pause replaced the saved task queue")
        frozen = self.frozen(sid)
        self.capture(page, "inflight_pause")
        latest = self.run.request("GET", f"/api/v1/sessions/{sid}/snapshot")
        gate = VersionGate()
        gate.require(latest["state"]["revision"], latest["state"]["epoch"])
        admitted = gate.admit(latest["display"]["revision"], latest["display"]["epoch"])
        rejected = not gate.admit(old["display"]["revision"], old["display"]["epoch"])
        if not admitted or not rejected:
            raise AssertionError("Production gate admitted stale captured display")
        self.checkpoint(
            "inflight_pause_and_display_replay",
            {
                "planning": planning,
                "paused": paused,
                "cancelled_job": cancelled,
                "frozen": frozen,
                "old_snapshot": old,
                "latest_snapshot": latest,
                "stale_replay_rejected": rejected,
                "scope": "production VersionGate real-packet replay",
            },
        )
        # Explicit protocol negative probe. Normal operator behavior stays on UI controls.
        response = self.run.client.post(
            f"/api/v1/sessions/{sid}/control/resume", json={"expected_revision": old["state"]["revision"]}
        )
        probe = {
            "status": response.status_code,
            "body": response.text,
            "sent_revision": old["state"]["revision"],
        }
        save(self.args.out / "stale_revision.json", probe)
        if response.status_code != 409 or self.state(sid) != paused:
            raise AssertionError("Stale revision was not rejected without mutation")
        self.checkpoint("stale_revision_protocol_negative", probe)
        first = self.send(page, sid, spec.task_contract.interrupt_instruction)
        if self.state(sid)["execution"] != "planning":
            raise AssertionError("First quick instruction already finished; race not exercised")
        second = self.send(page, sid, spec.initial_instruction)
        old_job = self.job(first, "superseded")
        new_job = self.job(second)
        state = self.control(page, sid, "暂停动作", "paused")
        expected = [
            (s.target_id, s.action, s.reference_id, s.angle_deg) for s in spec.task_contract.ordered_steps
        ]
        actual = [signature(task) for task in state["queue"] if task["semantic"]["task_role"] != "background"]
        if actual != expected:
            raise AssertionError("Latest quick instruction did not produce its ordered plan")
        self.checkpoint(
            "rapid_real_instructions",
            {"superseded": old_job, "committed": new_job, "final_state": state, "frozen": self.frozen(sid)},
        )

    def owned_api(self, name):
        directory = inside(os.environ["RUN_DIR"], root().resolve() / "runs" / "simulation")
        record = inside(directory / f"{name}_process.json", directory)
        data = json.loads(record.read_text(encoding="utf-8"))
        process = psutil.Process(data["pid"])
        if process.create_time() != data["create_time"] or Path(process.cwd()).resolve() != root().resolve():
            raise RuntimeError("Owned API process identity changed")
        if data["name"] != name or Path(data["cwd"]).resolve() != root().resolve():
            raise RuntimeError("Owned API record identity mismatch")
        command = data["command"]
        if command != ["bash", "scripts/run_simulation.sh", "api"]:
            raise RuntimeError(f"Refusing non-API service command: {command}")
        return data

    def helper(self, helper, *arguments, overrides=None):
        project = root().resolve()
        task_env = inside(self.args.task_env, project / ".work")
        helper = inside(helper, project / ".work")
        command = [
            "bash",
            "-c",
            'set -e; source "$1"; shift; exec "$@"',
            "holocue-fault-audit",
            str(task_env),
            "env",
            *(overrides or []),
            sys.executable,
            str(helper),
            *arguments,
        ]
        completed = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=65)
        self.counter += 1
        save(
            self.args.out / f"fault_command_{self.counter}.json",
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
        completed.check_returncode()

    def stop_api(self, name):
        identity = self.owned_api(name)
        self.fault_recovery_needed = True
        self.report["external_api_restart_required"] = True
        self.helper(self.args.stop_helper, name)
        if psutil.pid_exists(identity["pid"]):
            process = psutil.Process(identity["pid"])
            if process.create_time() == identity["create_time"] and process.status() != psutil.STATUS_ZOMBIE:
                raise RuntimeError("Owned API still running after stop helper")
        self.report["current_owned_api_service"] = None
        self.fault_recovery_needed = True
        save(self.args.out / "report.json", self.report)
        return identity

    def launch_api(self, suffix, model_url=None):
        name = "resilience_" + suffix + "_" + uuid.uuid4().hex[:8]
        self.created_api_services.append(name)
        self.report["test_created_api_services"] = list(self.created_api_services)
        overrides = ["HOLOCUE_MODEL_URL=" + model_url] if model_url else []
        self.helper(
            self.args.launch_helper,
            name,
            "--",
            "bash",
            "scripts/run_simulation.sh",
            "api",
            overrides=overrides,
        )
        self.report["current_owned_api_service"] = name
        save(self.args.out / "report.json", self.report)
        self.owned_api(name)

        def health():
            try:
                response = self.run.client.get("/health")
                return response.status_code == 200 and response.json()["backend_mode"] == "live"
            except httpx.TransportError:
                return False

        self.until("restarted live API health", health, bool, 45)
        self.fault_recovery_needed = bool(model_url)
        return name

    def restore_after_fault_failure(self):
        if self.fault_recovery_needed:
            name = self.report.get("current_owned_api_service")
            if name is not None:
                self.stop_api(name)
            self.launch_api("failure_cleanup")

    def stop_test_apis(self):
        stopped = []
        directory = inside(os.environ["RUN_DIR"], root().resolve() / "runs" / "simulation")
        for name in self.created_api_services:
            record = directory / f"{name}_process.json"
            if not record.exists():
                continue
            identity = json.loads(record.read_text(encoding="utf-8"))
            if psutil.pid_exists(identity["pid"]):
                process = psutil.Process(identity["pid"])
                if (
                    process.create_time() == identity["create_time"]
                    and process.status() != psutil.STATUS_ZOMBIE
                ):
                    self.stop_api(name)
            stopped.append(name)
        self.report["test_owned_api_stopped"] = True
        self.report["stopped_test_api_services"] = stopped
        self.report["current_owned_api_service"] = None
        self.report["external_api_restart_required"] = self.report.get("external_api_restart_required", False)
        self.fault_recovery_needed = False
        save(self.args.out / "report.json", self.report)

    def faults(self, sid, spec):
        page = self.pages[0]
        self.control(page, sid, "恢复任务", "running")
        prior = self.state(sid)
        stopped = self.stop_api(self.args.api_service)
        page.get_by_text("连接错误", exact=True).wait_for(timeout=15000)
        self.capture(page, "api_offline_visible_error")
        offline = self.frozen(sid)
        name = self.launch_api("restart")
        recovered = self.state(sid)
        if recovered["execution"] != "paused" or recovered["queue"] != prior["queue"]:
            raise AssertionError("API recovery did not preserve and pause tasks")
        frozen = self.frozen(sid)
        self.control(page, sid, "恢复任务", "running")
        continued = self.view(sid, time.time(), lambda row: row["clock_advancing"])
        self.control(page, sid, "暂停动作", "paused")
        self.checkpoint(
            "owned_api_restart_explicit_continue",
            {
                "stopped_identity": stopped,
                "prior": prior,
                "recovered": recovered,
                "offline": offline,
                "before_explicit_continue": frozen,
                "continued": continued,
            },
        )
        # Keep this TCP port bound without listening: real connects are refused and
        # another process cannot acquire the port during the fault interval.
        # No model process, shared service, response body or network route is modified.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            invalid_url = f"http://127.0.0.1:{port}/v1"
            self.stop_api(name)
            bad_name = self.launch_api("refused_model", invalid_url)
            try:
                self.open_session(page, sid)
                jid = self.send(page, sid, spec.initial_instruction)
                failure = self.job(jid, "error")
                failed = self.state(sid)
                if (
                    failed["execution"] != "error"
                    or "ConnectError:" not in failure["data"].get("error", "")
                    or "ConnectError:" not in (failed["last_error"] or "")
                ):
                    raise AssertionError("Expected real model connection refusal in job and state")
                page.get_by_text("执行错误", exact=False).first.wait_for(timeout=15000)
                self.capture(page, "model_refusal_visible_error")
                motion = self.frozen(sid)
            finally:
                self.stop_api(bad_name)
                self.launch_api("restored")
        unchanged = self.state(sid)
        if unchanged["execution"] != "error":
            raise AssertionError("Restoring model connectivity silently resumed old action")
        self.frozen(sid)
        self.open_session(page, sid)
        jid = self.send(page, sid, spec.initial_instruction)
        success = self.job(jid)
        self.control(page, sid, "暂停动作", "paused")
        self.checkpoint(
            "real_model_connection_failure_and_explicit_retry",
            {
                "fault_model_url": invalid_url,
                "failed_job": failure,
                "failed_state": failed,
                "frozen": motion,
                "restored_before_operator": unchanged,
                "explicit_retry_job": success,
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8750")
    parser.add_argument("--viewer", default="http://127.0.0.1:8780")
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scenes", nargs=2, default=["blocks", "connector"])
    parser.add_argument("--model-timeout", type=float, default=180)
    parser.add_argument("--faults", action="store_true")
    parser.add_argument("--api-service", help="Current owned API name in RUN_DIR; mandatory with --faults")
    parser.add_argument("--task-env", type=Path, default=root() / ".work/task_env.sh")
    parser.add_argument("--stop-helper", type=Path, default=root() / ".work/stop_owned.py")
    parser.add_argument("--launch-helper", type=Path, default=root() / ".work/launch_owned.py")
    args = parser.parse_args()
    if args.scenes[0] == args.scenes[1]:
        parser.error("Two different scenes are required")
    if args.faults and not args.api_service:
        parser.error("--faults requires --api-service")
    preflight(args)
    headers = (
        {"Authorization": "Bearer " + os.environ["HOLOCUE_API_KEY"]}
        if os.environ.get("HOLOCUE_API_KEY")
        else {}
    )
    options = {
        "headless": True,
        "args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    }
    if args.browser:
        options["executable_path"] = str(args.browser)
    with httpx.Client(base_url=args.api, timeout=10, headers=headers) as http:
        audit = Audit(args, http)
        try:
            health = audit.run.request("GET", "/health")
            if health["backend_mode"] != "live":
                raise ValueError("Real live model API required")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**options)
                try:
                    sessions = audit.establish(browser)
                    audit.isolation(sessions)
                    audit.invalidation(*sessions[0])
                    if args.faults:
                        try:
                            audit.faults(*sessions[0])
                        finally:
                            try:
                                audit.restore_after_fault_failure()
                            finally:
                                audit.stop_test_apis()
                    else:
                        audit.report["limitations"].append(
                            "API restart and model failure not run; enable --faults."
                        )
                    if audit.report["browser_errors"]:
                        raise AssertionError("Browser page errors observed")
                    audit.report["passed"] = True
                    audit.report["full_live_fault_coverage"] = args.faults
                finally:
                    for index, context in enumerate(audit.contexts):
                        if index < len(audit.pages) and not audit.pages[index].is_closed():
                            audit.capture(audit.pages[index], f"client_{index}_final")
                        context.tracing.stop(path=str(args.out / f"client_{index}_trace.zip"))
                        context.close()
                    browser.close()
        except Exception as error:
            audit.report["failure"] = {"type": type(error).__name__, "message": str(error)}
            raise
        finally:
            audit.report["finished_at"] = time.time()
            save(args.out / "report.json", audit.report)


if __name__ == "__main__":
    main()
