"""Summarize explicitly selected real camera runs without modifying raw evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
import statistics
import subprocess

from holocue.config import list_scenes, load_scene
from scripts.tests.live_twelve_scenes import signature


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(run, selection):
    available = {s["scene_id"] for s in list_scenes("reconstructed")}
    if set(selection) != available:
        raise AssertionError("Selection must cover exactly the twelve reconstructed scenes")
    rows, media = [], {}
    for sid, relative in selection.items():
        folder = (run / relative).resolve()
        if not folder.is_relative_to(run.resolve()):
            raise ValueError("Selected evidence is outside the run directory")
        result, video, final = [read(folder / f"{name}.json") for name in ("result", "video", "final")]
        spec = load_scene(sid, "reconstructed")
        if (final["session_id"], final["scene_id"], final["scene_set"]) != (
            result["session_id"],
            sid,
            "reconstructed",
        ):
            raise AssertionError(f"{sid}: final state does not belong to this result")
        if result["scene_id"] != sid or not result["passed"] or result["runtime_seconds"] > 180:
            raise AssertionError(f"{sid}: missing full minute-scale success")
        if final["queue"] or final["suspended"] or final["execution"] != "idle":
            raise AssertionError(f"{sid}: unfinished task")
        if len(final["completed"]) != len(spec.task_contract.ordered_steps) + 1:
            raise AssertionError(f"{sid}: explicit completion count differs")
        expected = [(spec.task_contract.interrupt_target, "inspect_back", None, None)] + [
            (step.target_id, step.action, step.reference_id, step.angle_deg)
            for step in spec.task_contract.ordered_steps
        ]
        if [signature(task) for task in final["completed"]] != expected:
            raise AssertionError(f"{sid}: completed tasks differ from the authored order")
        if not video["ok"] or not video["hook_restored"] or video["errors"]:
            raise AssertionError(f"{sid}: recording failure")
        gl = video["gl"]
        if any(s in gl["unmasked_renderer"].lower() for s in ("swiftshader", "llvmpipe", "softpipe")):
            raise AssertionError(f"{sid}: software rendering")
        # The first fixed-DPR batches predate the extra recorder diagnostic fields.
        # Their actual navigation URL and fixed encoded frame sizes remain evidence.
        initialization = read(folder.parent / "client_initialization.json")
        if "fixedDpr=1" not in initialization["viewer"]:
            raise AssertionError(f"{sid}: this selection used adaptive DPR")
        resolution = gl.get("resolution")
        if resolution and (resolution["renderer_pixel_ratio"] != 1 or resolution["fixed_dpr_setting"] != 1):
            raise AssertionError(f"{sid}: render DPR differs from 1")
        probe = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_frames",
                    "-show_entries",
                    "frame=best_effort_timestamp_time,width,height",
                    "-of",
                    "json",
                    str(folder / "video.webm"),
                ],
                text=True,
            )
        )
        frames = probe["frames"]
        pts = [float(f["best_effort_timestamp_time"]) for f in frames]
        if len(frames) != video["actual_copied_frames"] or len(frames) < 2:
            raise AssertionError(f"{sid}: encoded frame count mismatch")
        if any(b <= a for a, b in zip(pts, pts[1:])):
            raise AssertionError(f"{sid}: video timestamps do not advance")
        if any((f["width"], f["height"]) != (video["width"], video["height"]) for f in frames):
            raise AssertionError(f"{sid}: encoded dimensions change")
        span = pts[-1] - pts[0]
        if span < result["runtime_seconds"]:
            raise AssertionError(f"{sid}: video cannot cover the full runtime")
        timeline = [json.loads(line) for line in (folder / "timeline.jsonl").read_text().splitlines()]
        captures = result["model_input_images"] + [
            r["metadata"] for r in timeline if r["kind"] == "camera_export" and r["label"] != "final"
        ]
        row = {
            "scene_id": sid,
            "title": spec.title,
            "session_id": result["session_id"],
            "main_steps": result["main_steps"],
            "temporary_steps": result["temporary_steps"],
            "model_calls": result["model_calls"],
            "runtime_seconds": result["runtime_seconds"],
            "scene_setup_seconds": result["scene_setup_seconds"],
            "model_seconds": result["model_seconds"],
            "camera_online_seconds": sum(m["capture_and_save_s"] for m in captures),
            "camera_online_frames": len(captures),
            "video_seconds": span,
            "video_frames": len(frames),
            "video_max_frame_gap_seconds": max(b - a for a, b in zip(pts, pts[1:])),
            "render_dpr": 1,
            "hardware_renderer": gl["unmasked_renderer"],
            "evidence": relative,
            "dpr_receipt": "renderer_and_store"
            if resolution
            else "fixed_navigation_and_constant_video_dimensions",
        }
        rows.append(row)
        image_paths = [
            f"viewer/observations/{result['session_id']}/{m['image_file']}"
            for m in result["model_input_images"]
        ]
        media[sid] = {"video": relative + "/video.webm", "images": image_paths}
    if (
        sum(r["main_steps"] for r in rows) != 30
        or sum(r["temporary_steps"] for r in rows) != 12
        or sum(r["model_calls"] for r in rows) != 24
    ):
        raise AssertionError("The full 30+12 step / 24 call contract is incomplete")
    if len({row["session_id"] for row in rows}) != 12:
        raise AssertionError("Each selected scene must have a distinct session")
    totals = {
        key: sum(r[key] for r in rows)
        for key in [
            "runtime_seconds",
            "model_seconds",
            "camera_online_seconds",
            "camera_online_frames",
            "video_frames",
        ]
    }
    totals.update(
        min_runtime_seconds=min(r["runtime_seconds"] for r in rows),
        max_runtime_seconds=max(r["runtime_seconds"] for r in rows),
        median_runtime_seconds=statistics.median(r["runtime_seconds"] for r in rows),
    )
    return {
        "protocol": "runtime_camera_v1",
        "scene_set": "reconstructed",
        "render_dpr": 1,
        "playback_speed": 1,
        "all_twelve_passed": True,
        "rows": rows,
        "totals": totals,
        "media": media,
    }


def write(run, summary):
    (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = summary["rows"]
    with (run / "scenes.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    total = summary["totals"]
    lines = [
        "# HoloCue 轻量相机运行实测",
        "",
        "全部 12 个重构场景完成 30 个主步骤、12 个临时检查，共 24 次真实图文模型调用。保留显式暂停、恢复与完成确认，1.0 倍动作播放。",
        "",
        f"在线耗时范围 {total['min_runtime_seconds']:.1f}–{total['max_runtime_seconds']:.1f} 秒，中位数 {total['median_runtime_seconds']:.1f} 秒。十二场耗时之和 {total['runtime_seconds']:.1f} 秒；这不是一次并行作业的墙钟时长。",
        "",
        "在线时间从首次发送按钮点击前开始，包含输入相机捕获、模型推理、全部动作与控制和中间导图，直到最后一步显式确认及状态同步。场景初始化单列，Blender 离线审计不在此路径内。",
        "",
        "| 场景 | 主+临时步骤 | 在线秒 | 模型秒 | 相机捕获保存秒 | 场景准备秒 | 视频秒 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['scene_id']} | {row['main_steps']}+{row['temporary_steps']} | {row['runtime_seconds']:.1f} | {row['model_seconds']:.1f} | {row['camera_online_seconds']:.2f} | {row['scene_setup_seconds']:.1f} | {row['video_seconds']:.1f} |"
        )
    lines += [
        "",
        f"模型请求共 {total['model_seconds']:.1f} 秒；相机往返及保存共 {total['camera_online_seconds']:.1f} 秒，占所选在线时间总和 {100 * total['camera_online_seconds'] / total['runtime_seconds']:.1f}%。该项含网络、编码及保存，不是纯 GPU 渲染计时。剩余时间包含原动作时长、界面控制、状态同步及录像开销。",
        "",
        "Qwen3.5-4B 运行在 4029 的物理 GPU 1；Viser 客户端使用工作站 RTX 5070 Ti 的硬件 WebGL，经 SSH 连接服务。固定渲染 DPR=1；不是服务器上的软件浏览器性能，也不代表纯 CPU 部署达到同样速度。",
        "",
        "旧版 41 分钟视频来自含同步 Blender 原生审计和截图等待的慢速流程，且使用 0.1 倍动作播放和纯文本 Agent 输入。本报告使用真实相机 RGB，不将两种流程的差值称为同协议算法加速。",
        "",
        "原始选择在 selection.json；每场保留事件、原始 jobs、逐步快照、时钟时间线、实际相机 PNG 与 WebM。失败及早期 adaptive-DPR 试跑保留原目录，不计入这 12 个固定 DPR 结果。",
        "",
        "图文输入仍包含结构化对象和任务上下文。Viser 负责显示，Python 管理任务与运动学；本结果不等同纯视觉感知评测或接触动力学验证。",
    ]
    (run / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    cards = []
    for row in rows:
        item = summary["media"][row["scene_id"]]
        images = "".join(
            f'<a href="{html.escape(p)}"><img loading="lazy" src="{html.escape(p)}" alt="实际模型输入"></a>'
            for p in item["images"]
        )
        cards.append(
            f'<section><h2>{html.escape(row["scene_id"])}</h2><p>在线 {row["runtime_seconds"]:.1f} 秒 · {row["main_steps"]}+1 步 · 两次真实图文请求</p><video controls preload="metadata" src="{html.escape(item["video"])}"></video><div class="images">{images}</div><p><a href="{html.escape(row["evidence"])}/result.json">运行数据</a> · <a href="{html.escape(row["evidence"])}/jobs.json">原始模型记录</a></p></section>'
        )
    page = (
        '<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>HoloCue 真实相机运行结果</title><style>body{font:16px/1.6 system-ui;margin:32px auto;padding:0 20px;max-width:1100px;color:#17212c;background:#f6f7f9}h1{font-size:28px}section{background:white;padding:24px;margin:24px 0;border:1px solid #d7dce2;border-radius:8px}video{display:block;width:100%;max-height:650px;background:#fff}.images{display:flex;gap:12px;margin-top:14px}.images a{width:50%}img{width:100%}a{color:#1559a0}</style><h1>HoloCue · 真实相机运行结果</h1><p>12 场景，30 个主步骤 + 12 个临时检查。视频保留真实等待；下面两张图片是实际传给模型的相机输入。</p><p><a href="report.md">完整说明</a> · <a href="scenes.csv">耗时表 CSV</a></p>'
        + "".join(cards)
        + "</html>"
    )
    (run / "index.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    summary = summarize(args.run, read(args.run / "selection.json"))
    write(args.run, summary)
    print(json.dumps(summary["totals"], indent=2))


if __name__ == "__main__":
    main()
