#!/usr/bin/env python3
"""Record a fixed-camera demo video of the Viser front end (HoloCue).

Drives a scripted demonstration against a running holocue API + viewer, captures a
PNG frame sequence with headless Chromium (SwiftShader, same launch flags as
scripts/capture_viser.py), then assembles an H.264 video with ffmpeg.

Drive mode (chosen with --drive, recorded in the manifest):
  gui (default, preferred)  Real operator path: Playwright selects the scene in the
      "场景" dropdown, types the instruction into "输入任务", and clicks the four
      buttons (发送并更新任务/立即暂停/确认完成/继续). The viewer itself performs the
      expected_revision GET-then-POST against the backend, so the recording shows
      exactly what a user sees. The backend HTTP API is used by this script for
      READS only (health, session revision/execution polling to know when the GUI
      has settled); the viewer's session id is discovered from the store's
      `created` events because the API exposes no session listing endpoint.
  api      Script-driven backend calls (POST /messages + job polling, POST
      /control/*) against the viewer's own session, mirroring
      scripts/live_smoke.py; the viewer picks the changes up via its 0.2 s display
      poll. Kept as a fallback for runs where GUI automation is unavailable.
  Note: .venv-qa ships Playwright but no httpx, so the light HTTP reads use
  stdlib urllib against the same endpoints (no arbitrary remote execution).

Camera policy: absolutely no camera moves. The script never touches camera
controls, never scrolls the 3D viewport, and never clicks viewer toolbar buttons
("Reset View" etc.). The camera stays at the server-side render_hints.fit_camera
pose applied on scene load / client connect. Verify by comparing the first and
last frames.

Usage:
  .venv-qa/bin/python scripts/capture_viser_demo.py \
      --api http://127.0.0.1:8750 --url http://127.0.0.1:8780 \
      --scene control_panel --steps steps.json \
      --outdir runs/engine_round/viser_shots \
      --out runs/engine_round/engine_bay_viser_demo.mp4 \
      --width 1680 --height 945 --hold 2.5 --fps 12 --env .venv-qa

steps.json: [{"action":"wait","s":3}, {"action":"message","text":"..."},
             {"action":"pause"}, {"action":"complete"}, {"action":"resume"}]
"message" may carry "expect": a substring the assistant_message should contain.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Default embedded script: engine_bay demo for the engine round. Content is a
# template only -- what actually runs is always fully decided by --steps (or this
# default when --steps is omitted). engine_bay must exist in configs/scenes by then.
DEFAULT_STEPS = [
    {"action": "wait", "s": 3},
    {"action": "message",
     "text": "把 CLAMP 逆时针转 90 度，接着把 PLUG 插进 PLUGPORT，最后检查 CONN 的背面。"},
    {"action": "wait", "s": 4},
    {"action": "complete"},
    {"action": "message", "text": "先别管卡箍，直接看 CONN 的背面。"},
    {"action": "wait", "s": 4},
    {"action": "complete"},
    {"action": "resume"},
]

DRIVE_MODE_NOTE = {
    "gui": "网页 GUI 真实交互（下拉选场景/输入指令/点击按钮组），viewer 自身携带 expected_revision 提交；脚本仅经 API 只读轮询 revision/execution 判断画面稳定。",
    "api": "脚本直接调用后端 HTTP API（POST /messages 轮询 job、POST /control/*，expected_revision 乐观并发，参照 scripts/live_smoke.py），viewer 经 0.2s display 轮询呈现。",
}


def log(msg: str) -> None:
    print(f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def http_json(method: str, url: str, payload: dict | None = None, timeout: float = 15.0):
    """Small stdlib JSON client (visible errors, raw bodies preserved)."""
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = Request(url, data=data, method=method,
                  headers={"Content-Type": "application/json"} if data else {})
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {body}") from e


class Backend:
    """Read helpers + optional API-drive writes against the viewer's session."""

    def __init__(self, api: str, root: Path, scene_id: str):
        self.api = api.rstrip("/")
        self.db = root / "runs" / "state.sqlite"
        self.scene_id = scene_id
        self.sid: str | None = None

    def health(self) -> dict:
        return http_json("GET", self.api + "/health")

    def session(self) -> dict:
        assert self.sid
        return http_json("GET", f"{self.api}/api/v1/sessions/{self.sid}")

    def events_max_seq(self) -> int:
        con = sqlite3.connect(self.db, timeout=10)
        try:
            row = con.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()
            return int(row[0])
        finally:
            con.close()

    def discover_sid(self, after_seq: int, timeout: float = 30.0) -> str:
        """The API has no session-list endpoint; read the store's `created` events
        (read-only) and take the newest session created after `after_seq` for the
        target scene -- that is the session the viewer just created for itself."""
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            con = sqlite3.connect(self.db, timeout=10)
            try:
                rows = con.execute(
                    "SELECT seq, data FROM events WHERE kind='created' AND seq>? ORDER BY seq",
                    (after_seq,)).fetchall()
            finally:
                con.close()
            for seq, data in reversed(rows):
                d = json.loads(data)
                if d.get("scene_id") == self.scene_id:
                    self.sid = d["session_id"]
                    log(f"viewer session discovered: {self.sid[:8]}… (event seq {seq})")
                    return self.sid
            time.sleep(0.25)
        raise TimeoutError(f"No new session created for scene {self.scene_id}")

    def post_message(self, text: str, timeout: float = 150.0) -> dict:
        assert self.sid
        rev = self.session()["revision"]
        job = http_json("POST", f"{self.api}/api/v1/sessions/{self.sid}/messages",
                        {"text": text, "request_id": uuid.uuid4().hex,
                         "expected_revision": rev})
        t0 = time.perf_counter()
        while True:
            job = http_json("GET", f"{self.api}/api/v1/jobs/{job['id']}")
            if job["status"] != "planning":
                return job
            if time.perf_counter() - t0 > timeout:
                raise TimeoutError(f"job {job['id']} still planning after {timeout}s")
            time.sleep(0.3)

    def post_control(self, operation: str) -> dict:
        assert self.sid
        rev = self.session()["revision"]
        return http_json("POST", f"{self.api}/api/v1/sessions/{self.sid}/control/{operation}",
                         {"expected_revision": rev})


def wait_state(backend: Backend, want_revision: int, expect_exec: tuple[str, ...],
               timeout: float, what: str) -> dict:
    """Poll the session until revision advances and execution matches. Raw errors
    are surfaced, never substituted."""
    t0 = time.perf_counter()
    last = {}
    while time.perf_counter() - t0 < timeout:
        last = backend.session()
        if last.get("revision", 0) >= want_revision and last.get("execution") in expect_exec:
            return last
        if last.get("execution") == "error" and last.get("revision", 0) >= want_revision:
            raise RuntimeError(f"{what}: backend reported error: {last.get('last_error')}")
        time.sleep(0.2)
    raise TimeoutError(f"{what}: waited for revision>={want_revision} execution in "
                       f"{expect_exec}, got revision={last.get('revision')} "
                       f"execution={last.get('execution')} last_error={last.get('last_error')}")


class Page:
    """Playwright wrapper. Only GUI-panel interactions; camera is never touched."""

    def __init__(self, pw, url: str, width: int, height: int):
        self.browser = pw.chromium.launch(
            headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        self.page = self.browser.new_page(
            viewport={"width": width, "height": height}, device_scale_factor=1)
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(6000)  # viser assets + first render
        self._dismiss_notifications()

    def _dismiss_notifications(self):
        for btn in self.page.locator('[class*="Notification-closeButton"]').all():
            try:
                btn.click(timeout=1500)
            except Exception:
                pass

    def body_text(self) -> str:
        return self.page.evaluate("() => document.body.innerText")

    def wait_dom(self, predicate, timeout: float, what: str) -> str:
        t0 = time.perf_counter()
        text = self.body_text()
        while not predicate(text) and time.perf_counter() - t0 < timeout:
            self.page.wait_for_timeout(200)
            text = self.body_text()
        if not predicate(text):
            raise TimeoutError(f"DOM never showed: {what}; last text head: {text[:300]!r}")
        return text

    def select_scene(self, known_titles: list[str], target_title: str):
        """Pick the 场景 dropdown: the combobox whose current value is a known
        scene title (the other comboboxes are viewer settings)."""
        boxes = self.page.locator('input[class*="mantine-Select-input"]')
        n = boxes.count()
        idx = None
        current = None
        for i in range(n):
            v = boxes.nth(i).input_value()
            if v in known_titles:
                idx, current = i, v
                break
        if idx is None:
            raise RuntimeError(f"场景 dropdown not found (no combobox holds a scene title)")
        if current != target_title:
            boxes.nth(idx).click()
            options = self.page.get_by_role("option", name=target_title, exact=True)
            options.first.click(timeout=8000)
        return current

    def set_command(self, text: str):
        boxes = self.page.locator('input[class*="mantine-TextInput-input"]')
        n = boxes.count()
        idx = None
        for i in range(n):
            v = boxes.nth(i).input_value()
            if not v.startswith("ws://"):
                idx = i
                break
        if idx is None:
            raise RuntimeError("输入任务 text box not found")
        box = boxes.nth(idx)
        box.fill(text)
        box.press("Enter")  # viser text inputs commit on Enter/blur
        if box.input_value() != text:
            raise RuntimeError("command text did not stick in the GUI input")

    def click_action(self, label: str):
        self.page.get_by_role("button", name=label, exact=True).first.click(timeout=8000)

    def screenshot(self, path: Path):
        self.page.screenshot(path=str(path))  # viewport-sized, camera untouched

    def close(self):
        self.browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parent
    ap.add_argument("--api", default="http://127.0.0.1:8750")
    ap.add_argument("--url", default="http://127.0.0.1:8780")
    ap.add_argument("--scene", default="control_panel")
    ap.add_argument("--steps", default=None, help="steps.json; omit for the embedded engine_bay default script")
    ap.add_argument("--outdir", default="runs/engine_round/viser_shots")
    ap.add_argument("--out", default="runs/engine_round/engine_bay_viser_demo.mp4")
    ap.add_argument("--width", type=int, default=1680)
    ap.add_argument("--height", type=int, default=945)
    ap.add_argument("--hold", type=float, default=2.5, help="seconds each frame holds in the video")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--env", default=".venv-qa", help="project venv providing Playwright; re-exec into it if needed")
    ap.add_argument("--drive", choices=("gui", "api"), default="gui")
    ap.add_argument("--shot-times", default="1.0,2.2,3.4",
                    help="post-action screenshot times in seconds (ghost animation progress)")
    ap.add_argument("--settle", type=float, default=0.8, help="extra settle after DOM confirms an update")
    ap.add_argument("--timeout", type=float, default=150.0, help="per-action wait timeout")
    ap.add_argument("--root", default=os.environ.get("HOLOCUE_ROOT") or str(here.parent))
    args = ap.parse_args()

    # Re-exec into the QA env when Playwright is missing here (e.g. run by .venv).
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        py = Path(args.env) if Path(args.env).is_absolute() else here.parent / args.env
        py = py / "bin" / "python"
        if py.exists():
            log(f"playwright missing in {sys.executable}; re-exec into {py}")
            os.execv(str(py), [str(py), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit(f"playwright unavailable and {py} not found")

    from playwright.sync_api import sync_playwright

    root = Path(args.root).resolve()
    steps = json.loads(Path(args.steps).read_text(encoding="utf-8")) if args.steps else DEFAULT_STEPS
    shot_times = sorted(float(x) for x in args.shot_times.split(",") if x.strip())
    outdir, out = Path(args.outdir).resolve(), Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)

    log(f"drive mode: {args.drive} -- {DRIVE_MODE_NOTE[args.drive]}")
    health = http_json("GET", args.api + "/health")
    log(f"backend health: {health}")
    scenes = {s["title"]: s for s in http_json("GET", args.api + "/api/v1/scenes")}
    scene_info = next((s for s in scenes.values() if s["scene_id"] == args.scene), None)
    if scene_info is None:
        raise SystemExit(f"scene {args.scene!r} not in /api/v1/scenes: {sorted(s['scene_id'] for s in scenes.values())}")

    manifest = {
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "drive_mode": args.drive, "drive_mode_note": DRIVE_MODE_NOTE[args.drive],
        "api": args.api, "url": args.url, "health": health,
        "scene": args.scene, "viewport": [args.width, args.height],
        "hold_s": args.hold, "fps": args.fps, "shot_times_s": shot_times,
        "camera_policy": "fixed: no camera controls touched, no 3D-viewport scrolling; "
                         "camera stays at the fit_camera pose set on scene load",
        "steps": steps, "frames": [],
    }
    backend = Backend(args.api, root, args.scene)
    frames: list[dict] = []

    def snap(action: str, label: str, state: dict | None):
        name = f"shot_{len(frames) + 1:04d}_{label}.png"
        page.screenshot(outdir / name)
        frames.append({"file": name, "action": action, "label": label,
                       "t": round(time.perf_counter(), 3),
                       "revision": state.get("revision") if state else None,
                       "execution": state.get("execution") if state else None,
                       "assistant_message": state.get("assistant_message") if state else None})
        log(f"shot {name}  (rev={state.get('revision') if state else '-'} "
            f"exec={state.get('execution') if state else '-'})")

    os.environ["CUDA_VISIBLE_DEVICES"] = ""  # browser renders on CPU (SwiftShader)
    with sync_playwright() as pw:
        page = Page(pw, args.url, args.width, args.height)
        try:
            page.wait_dom(lambda t: "状态" in t and "版本" in t, 20, "task panel status line")
            baseline_seq = backend.events_max_seq()
            known_titles = list(scenes)
            log(f"selecting scene {args.scene} ({scene_info['title']!r}) via 场景 dropdown")
            current = page.select_scene(known_titles, scene_info["title"])
            if current == scene_info["title"]:
                # Already on the target scene: a no-op switch would fire no event and
                # leave no fresh session to record. Switch away and back.
                other = next(t for t in known_titles if t != scene_info["title"])
                log(f"already on {current!r}; switching via {other!r} to force a fresh session")
                page.select_scene(known_titles, other)
                page.wait_dom(lambda t: other in t, 20, f"intermediate scene {other!r}")
                page.page.wait_for_timeout(1200)
                page.select_scene(known_titles, scene_info["title"])
            backend.discover_sid(baseline_seq)
            page.wait_dom(lambda t: scene_info["title"] in t and "版本 0" in t, 30,
                          f"scene {scene_info['title']} loaded at revision 0")
            page.page.wait_for_timeout(int(args.settle * 1000))
            state = backend.session()
            snap("scene", f"scene_{args.scene}", state)

            for si, step in enumerate(steps):
                act = step.get("action")
                if act == "wait":
                    secs = float(step.get("s", 1))
                    n = max(1, int(secs + 0.999))
                    log(f"step {si}: wait {secs}s -> {n} frames (1/s)")
                    for k in range(1, n + 1):
                        page.page.wait_for_timeout(int(1000 * (secs / n)))
                        snap("wait", f"wait{si}_{k}", backend.session())
                    continue

                pre = backend.session()
                want_exec = {"pause": ("paused",),
                             "complete": ("running", "idle"),
                             "resume": ("running", "idle"),
                             # a planner decision may itself pause (clarify/pause ops)
                             "message": ("running", "idle", "paused")}[act]
                if act == "message":
                    text = step["text"]
                    if args.drive == "gui":
                        page.set_command(text)
                        page.click_action("发送并更新任务")
                        state = wait_state(backend, pre["revision"] + 2, want_exec,
                                           args.timeout, f"message {text[:24]!r}")
                    else:
                        job = backend.post_message(text)
                        if job["status"] != "done":
                            raise RuntimeError(f"message job ended as {job['status']}: "
                                               f"{json.dumps(job.get('data', {}), ensure_ascii=False)[:600]}")
                        state = wait_state(backend, pre["revision"] + 2, want_exec,
                                           args.timeout, f"message {text[:24]!r}")
                    expect = step.get("expect")
                    if expect:
                        if expect not in state.get("assistant_message", ""):
                            raise RuntimeError(f"assistant_message missing {expect!r}: "
                                               f"{state.get('assistant_message')!r}")
                        page.wait_dom(lambda t: expect in t, 10, f"assistant text {expect!r}")
                    else:
                        page.wait_dom(lambda t: f"版本 {state['revision']}" in t, 10,
                                      f"revision {state['revision']} in status line")
                elif act in ("pause", "complete", "resume"):
                    if args.drive == "gui":
                        page.click_action({"pause": "立即暂停", "complete": "确认完成",
                                           "resume": "继续"}[act])
                    else:
                        backend.post_control(act)
                    state = wait_state(backend, pre["revision"] + 1, want_exec,
                                       args.timeout, act)
                    page.wait_dom(lambda t: f"版本 {state['revision']}" in t, 10,
                                  f"revision {state['revision']} in status line")
                else:
                    raise SystemExit(f"unknown step action {act!r}")
                page.page.wait_for_timeout(int(args.settle * 1000))
                log(f"step {si}: {act} done -> shots at {shot_times}s "
                    f"(rev {pre['revision']}->{state['revision']}, exec {state['execution']})")
                t0 = time.perf_counter()
                for t in shot_times:
                    remain = t - (time.perf_counter() - t0)
                    if remain > 0:
                        page.page.wait_for_timeout(int(remain * 1000))
                    snap(act, f"{act}{si}_t{t:g}", backend.session())
        except Exception as e:
            err_shot = outdir / f"error_{len(frames) + 1:04d}.png"
            try:
                page.screenshot(err_shot)
                manifest["error_shot"] = err_shot.name
            except Exception:
                pass
            manifest["error"] = f"{type(e).__name__}: {e}"
            manifest["frames"] = frames
            (outdir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=1))
            page.close()
            raise
        page.close()

    # Assemble: each frame holds `hold` seconds; concat demuxer + fps filter -> CFR h264.
    lst = outdir / "ffmpeg_list.txt"
    lines = ["ffconcat version 1.0"]
    for f in frames:
        lines += [f"file '{(outdir / f['file']).as_posix()}'", f"duration {args.hold}"]
    if frames:  # concat quirk: final entry repeated so its duration is honored
        lines.append(f"file '{(outdir / frames[-1]['file']).as_posix()}")
    lst.write_text("\n".join(lines) + "\n")
    # yuv420p needs even dimensions (e.g. 1680x945 -> padded 1680x946); pad is a
    # no-op when width/height are already even.
    vf = (f"fps={args.fps},scale={args.width}:{args.height}:flags=lanczos,"
          f"pad=ceil(iw/2)*2:ceil(ih/2)*2:(ow-iw)/2:(oh-ih)/2,format=yuv420p")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-vf", vf, "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", str(out)]
    log("encoding: " + " ".join(cmd))
    enc = subprocess.run(cmd, capture_output=True, text=True)
    if enc.returncode != 0:
        (outdir / "ffmpeg_error.log").write_text(enc.stderr[-8000:])
        raise RuntimeError(f"ffmpeg failed ({enc.returncode}); stderr tail in "
                           f"{outdir / 'ffmpeg_error.log'}: {enc.stderr.strip()[-500:]}")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=codec_name,width,height,r_frame_rate,pix_fmt",
         "-of", "json", str(out)], check=True, capture_output=True, text=True).stdout
    summary = json.loads(probe)
    manifest["frames"] = frames
    manifest["video"] = {"path": str(out), "probe": summary,
                         "finished_at": _dt.datetime.now().isoformat(timespec="seconds")}
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    log(f"video: {out}")
    log(f"probe: {json.dumps(summary['streams'][0], ensure_ascii=False)} "
        f"duration={float(summary['format']['duration']):.2f}s "
        f"size={int(summary['format']['size']) // 1024}KiB")
    log(f"manifest: {outdir / 'manifest.json'}  frames: {len(frames)}")


if __name__ == "__main__":
    main()
