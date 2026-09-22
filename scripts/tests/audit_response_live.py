"""Native Viser N/sigma response through real model plans and visible controls."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

import httpx
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

from holocue.config import root, load_scene
from scripts.tests.audit_viewer_live import BrowserRun, ui_input, wait_view, assert_comparable_captures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    spec = load_scene("control_panel")
    instructions = [
        (
            "count_high",
            "整体替换计划：检查 C 的背面，C 为当前操作，优先级 5，精确定位 precise；持续保留 B 的背景标签提示，B 优先级 1，persistent。",
            5000,
            1.0,
        ),
        (
            "count_low",
            "整体替换计划：仍检查 C 的背面，C 为当前操作，优先级 1，精确定位 precise；持续保留 B 的背景标签提示，B 优先级 5，persistent。",
            1000,
            1.0,
        ),
        (
            "sigma_wide",
            "整体替换计划：仍检查 C 的背面，C 为当前操作，优先级 1，显示需求明确使用普通上下文 neutral；持续保留 B 的背景标签提示，B 优先级 5，persistent。",
            1000,
            4.0,
        ),
    ]
    with httpx.Client(base_url="http://127.0.0.1:8750", timeout=10) as http, sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000}, record_video_dir=str(args.out / "video")
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        run = BrowserRun(page, http, args.out)
        try:
            page.goto("http://127.0.0.1:8780", wait_until="networkidle")
            software_notice = page.get_by_role("alert").filter(has_text="Software WebGL rendering detected")
            if software_notice.count():
                software_notice.get_by_role("button").click()
            page.get_by_role("tab", name="任务", exact=True).wait_for(timeout=60000)
            page.get_by_role("tab", name="任务", exact=True).click()
            deadline = time.monotonic() + 60
            while True:
                initial_sid = ui_input(page, "会话标识").input_value()
                if initial_sid:
                    wait_view(initial_sid, 0, revision=0)
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("Initial scene did not become ready")
                page.wait_for_timeout(100)
            page.get_by_role("combobox", name="场景", exact=True).click()
            page.get_by_role("option", name=spec.title, exact=True).click()
            deadline = time.monotonic() + 30
            while True:
                sid = ui_input(page, "会话标识").input_value()
                if sid and run.state(sid)["scene_id"] == spec.scene_id:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("Scene selection did not create a session")
                page.wait_for_timeout(100)
            focus = None
            for name, instruction, count, sigma in instructions:
                planned = run.message(sid, instruction)
                state = run.control(sid, "pause")
                snapshot = run.read.request("GET", f"/api/v1/sessions/{sid}/snapshot")
                if ui_input(page, "会话标识").input_value() != sid:
                    raise AssertionError("Response experiment changed the UI session")
                for packet in (state, snapshot["state"], snapshot["display"]):
                    if (
                        packet["session_id"],
                        packet["scene_id"],
                        packet["revision"],
                        packet["epoch"],
                        packet["execution"],
                    ) != (sid, spec.scene_id, state["revision"], state["epoch"], "paused"):
                        raise AssertionError(
                            "Response experiment has inconsistent paused state/display identity"
                        )
                if state["revision"] <= planned["revision"] or (
                    rows and planned["revision"] <= rows[-1]["view"]["revision"]
                ):
                    raise AssertionError("Response experiment did not advance through a new plan and pause")
                cue = next(c for c in snapshot["display"]["cues"] if c["target_id"] == "C")
                if (cue["action"], cue["task_role"], cue["n_gaussians"], cue["sigma_value"]) != (
                    "inspect_back",
                    "current",
                    count,
                    sigma,
                ):
                    raise AssertionError(
                        "Real model did not produce the requested response experiment: " + json.dumps(cue)
                    )
                page.get_by_role("tab", name="观察", exact=True).click()
                if focus is None:
                    run.set_render_pixel_ratio("1.0")
                    ui_input(page, "跟随当前步骤").uncheck()
                    page.get_by_role("combobox", name="观察对象", exact=True).click()
                    page.get_by_role("option", name="C", exact=True).click()
                    before = run.view_button("结构检查")
                    wait_view(sid, before, "inspection", revision=state["revision"])
                    page.get_by_role("button", name="聚焦选中对象", exact=True).click()
                    view = wait_view(sid, time.time(), "inspection", revision=state["revision"])
                    # Use the Number control's 0.005 m step. Filling its already
                    # rounded display string may emit no change even though the
                    # automatic focus retains more precision on the server.
                    focus = float(f"{round(view['focus_m'] / 0.005) * 0.005:.3f}")
                    run.record(
                        "fixed_camera_selected",
                        target_id="C",
                        mode="inspection",
                        automatic_focus_m=view["focus_m"],
                        requested_focus_m=focus,
                    )
                # Re-selecting the view fits the new cue envelope and invalidates
                # a fixed-camera N/sigma comparison. Later plans reuse this view.
                if ui_input(page, "跟随当前步骤").is_checked():
                    raise AssertionError("Response experiment enabled automatic camera following")
                page.get_by_role("tab", name="显示响应", exact=True).click()
                ui_input(page, "焦点数值 米").fill(str(focus))
                ui_input(page, "焦点数值 米").press("Tab")
                ui_input(page, "亮度数值").fill("1")
                ui_input(page, "亮度数值").press("Tab")
                deadline = time.monotonic() + 10
                while True:
                    view = wait_view(sid, time.time(), "inspection", revision=state["revision"])
                    if np.isclose(view["focus_m"], focus, rtol=0, atol=1e-9) and np.isclose(
                        view["brightness"], 1.0, rtol=0, atol=1e-9
                    ):
                        break
                    if time.monotonic() > deadline:
                        raise AssertionError(
                            "Visible focus/brightness controls did not settle: " + json.dumps(view)
                        )
                    page.wait_for_timeout(100)
                visible_focus = float(ui_input(page, "焦点数值 米").input_value())
                if not np.isclose(visible_focus, focus, rtol=0, atol=1e-9):
                    raise AssertionError("Visible focus control differs from the fixed focus")
                if (
                    view["session_id"],
                    view["scene_id"],
                    view["revision"],
                    view["epoch"],
                    view["execution"],
                    view["view_mode"],
                    view["selected_id"],
                    view["clock_advancing"],
                ) != (
                    sid,
                    spec.scene_id,
                    state["revision"],
                    state["epoch"],
                    "paused",
                    "inspection",
                    "C",
                    False,
                ):
                    raise AssertionError("Response comparison view is not the current paused C inspection")
                if not np.isclose(view["focus_m"], focus) or not np.isclose(view["brightness"], 1.0):
                    raise AssertionError("Response comparison did not apply the fixed focus and brightness")
                run.record(
                    "fixed_camera_response",
                    name=name,
                    revision=view["revision"],
                    epoch=view["epoch"],
                    mode=view["view_mode"],
                    selected_id=view["selected_id"],
                    view=view,
                )
                page.wait_for_timeout(400)
                canvas = page.locator("canvas[data-engine]").bounding_box()
                if canvas is None or canvas["width"] < 100:
                    raise AssertionError("The native three.js canvas is not visible")
                shot = run.capture(
                    f"{name}.png",
                    stable=True,
                    expected_response={"focus_m": focus, "brightness": 1.0},
                    clip=canvas,
                )
                view = shot["view_after"]
                row = {
                    "name": name,
                    "instruction": instruction,
                    "session_id": sid,
                    "view": view,
                    "snapshot": snapshot,
                    "planned_revision": planned["revision"],
                    "follow_current_step": False,
                    "camera_setup": "initial_selection" if not rows else "reuse_without_refit",
                    "canvas_box": canvas,
                    "viewport": page.viewport_size,
                    "stable_shot": shot,
                }
                rows.append(row)
                (args.out / f"{name}.json").write_text(json.dumps(row, ensure_ascii=False, indent=2))
            arrays = [
                np.asarray(Image.open(args.out / f"{row['name']}.png").convert("RGB")).astype(int)
                for row in rows
            ]
            differences = []
            for left, right in ((0, 1), (1, 2)):
                assert_comparable_captures(
                    rows[left]["stable_shot"], rows[right]["stable_shot"], new_revision=True
                )
                for key in (
                    "position_m",
                    "look_at_m",
                    "up_direction",
                    "fov_rad",
                    "aspect",
                    "focus_m",
                    "brightness",
                ):
                    if not np.allclose(rows[left]["view"][key], rows[right]["view"][key]):
                        raise AssertionError("Response comparison changed camera or brightness: " + key)
                changed = int((np.abs(arrays[left] - arrays[right]).max(axis=2) > 3).sum())
                if changed < 20:
                    raise AssertionError("N/sigma did not change the native canvas")
                differences.append(
                    {
                        "from": rows[left]["name"],
                        "to": rows[right]["name"],
                        "changed_pixels": changed,
                        "metric_scope": "Whole-canvas changed pixels; not a locality or spatial-support measurement.",
                    }
                )
            if errors:
                raise AssertionError(errors)
            (args.out / "report.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "session_id": sid,
                        "differences": differences,
                        "browser_errors": errors,
                        "parameter_source": ["configs/display_policy.json", "configs/preview_response.json"],
                        "render_pixel_ratio": "1.0 selected through the existing visible Viser setting; product default remains Adaptive",
                        "method": "Real model priority/depth requirements; native fixed-camera inspection controls",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
