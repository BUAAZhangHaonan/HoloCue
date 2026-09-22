"""Build a local gallery from actual mesh renders and analytical splat images."""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from holocue.config import root, list_scenes, load_scene, load_policy
from holocue.models import CueSemantic, Decision, Session
from holocue.projection import packet
from holocue.response import splat_arrays, camera_aligned_rgba, profile, envelope
from holocue.state import apply_decision


def annotated(image, text):
    out = Image.new("RGB", (image.width, image.height + 40), (234, 240, 244))
    out.paste(image, (0, 40))
    draw = ImageDraw.Draw(out)
    draw.text((12, 10), text, font=ImageFont.truetype("DejaVuSans.ttf", 17), fill=(32, 50, 65))
    return out


def response_evidence(output):
    spec = load_scene("control_panel")
    decision = Decision(
        operation="replace",
        assistant_message="Evaluate display response",
        cues=[
            CueSemantic(
                target_id="B",
                action="rotate",
                angle_deg=30,
                cue_type="ring_arrow",
                task_role="current",
                priority=5,
                depth_requirement="precise",
                instruction="Rotate B by 30 degrees",
            )
        ],
    )
    state = apply_decision(
        Session(session_id="optical-envelope", scene_id=spec.scene_id, backend_mode="analytical_validation"),
        decision,
        spec,
    )
    cue = packet(state, spec, load_policy()).cues[0]
    look = np.asarray(cue.pose.position_m) + np.array([0, -0.022, 0.042])
    position = look + np.array([0.05, -0.27, 0.27])
    focal_distance = float(np.linalg.norm(position - look))

    def image(sigma, defocus, brightness):
        configured = cue.model_copy(update={"sigma_value": sigma})
        centers, cov, rgb, opacity = splat_arrays(
            spec, configured, configured.pose, position, look, focal_distance + defocus, brightness
        )
        rgba = Image.fromarray(
            camera_aligned_rgba(centers, cov, opacity, rgb, configured.pose, position, look, size=(480, 320))
        )
        background = Image.new("RGBA", rgba.size, (24, 32, 39, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB"), float(opacity.sum())

    sheet = Image.new("RGB", (1440, 1080), (234, 240, 244))
    measurements = []
    for row, sigma in enumerate((1.0, 2.5, 4.0)):
        for column, defocus in enumerate((0.0, 0.12, 0.35)):
            raster, alpha = image(sigma, defocus, 1.0)
            caption = f"sigma {sigma:g}   focus offset {defocus:.2f} m"
            sheet.paste(annotated(raster, caption), (column * 480, row * 360))
            width, peak, rayleigh = envelope(sigma, defocus, profile())
            measurements.append(
                {
                    "sigma": sigma,
                    "defocus_m": defocus,
                    "waist_width_m": float(width),
                    "peak": float(peak),
                    "rayleigh_m": rayleigh,
                    "sum_splat_alpha": alpha,
                }
            )
    sheet.save(output / "response_focus_sigma.png")
    brightness_sheet = Image.new("RGB", (1440, 360), (234, 240, 244))
    brightness_images = []
    for column, value in enumerate((0.0, 0.25, 1.0)):
        raster, _ = image(1.0, 0.0, value)
        brightness_images.append(np.asarray(raster))
        brightness_sheet.paste(annotated(raster, f"brightness {value:g}"), (column * 480, 0))
    if not all(
        np.abs(brightness_images[i + 1].astype(float) - brightness_images[i]).mean() > 0 for i in range(2)
    ):
        raise AssertionError("brightness did not change the actual raster")
    brightness_sheet.save(output / "response_brightness.png")
    frames = []
    for value in np.linspace(-0.05, 0.40, 32):
        raster, _ = image(1.0, float(value), 1.0)
        frames.append(annotated(raster, f"Analytical focus scan   offset {value:+.3f} m"))
    frames[0].save(
        output / "response_focus_scan.gif", save_all=True, append_images=frames[1:], duration=100, loop=0
    )
    (output / "response_measurements.json").write_text(
        json.dumps(
            {
                "profile": profile().model_dump(),
                "input_boundary": "declared display parameters",
                "model_backend_exercised": False,
                "renderer": "reference raster of actual Gaussian arrays",
                "measurements": measurements,
            },
            indent=2,
        )
    )


def main():
    output = root() / "runs/simulation/rendered"
    output.mkdir(parents=True, exist_ok=True)
    response_evidence(output)
    ids = [s["scene_id"] for s in list_scenes()]
    reports = []
    for sid in ids:
        reports.append(json.loads((output / sid / f"{sid}_render.json").read_text()))
    (output / "report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    for suffix in ("overview", "front", "detail", "inspection"):
        sheet = Image.new("RGB", (1920, 1920), (234, 240, 244))
        for index, sid in enumerate(ids):
            image = Image.open(output / sid / f"{sid}_{suffix}.png")
            image.thumbnail((640, 475))
            sheet.paste(image, ((index % 3) * 640, (index // 3) * 480))
        name = "twelve_scenes.png" if suffix == "overview" else f"twelve_{suffix}.png"
        sheet.save(output / name)
    cards = []
    for sid in ids:
        spec = load_scene(sid)
        images = "".join(
            f'<a href="{sid}/{sid}_{view}.png"><img src="{sid}/{sid}_{view}.png" alt="{sid} {view}"></a>'
            for view in ("overview", "front", "detail", "inspection")
        )
        steps = "".join(
            f"<li>{html.escape(s.target_id)} {html.escape(s.action)} {html.escape(s.reference_id or '')}</li>"
            for s in spec.task_contract.ordered_steps
        )
        cards.append(
            f"<section><h2>{html.escape(spec.title)}</h2><p>{html.escape(spec.task_contract.setting)}</p>"
            f'<ol>{steps}</ol><div class="views">{images}</div></section>'
        )
    page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HoloCue 仿真检查</title><style>body{margin:auto;max-width:1440px;padding:30px;background:#edf2f5;color:#203442;font:17px system-ui;line-height:1.7}section{background:white;margin:24px 0;padding:24px;border-radius:12px}.views{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}img{width:100%;height:auto}h1,h2{line-height:1.3}@media(max-width:850px){.views{grid-template-columns:1fr}}</style>
<h1>HoloCue 十二场景仿真检查</h1><p>以下图片来自实际 GLB 网格的 VTK OSMesa 软件渲染。每个场景包含工作区域、正面、操作特写和检查面。点击图片可以查看原始分辨率。</p>
<section><h2>Gaussian 显示响应</h2><p>此处使用已声明的解析包络参数，展示焦点、宽度和亮度对提示图像的影响。</p><img src="response_focus_sigma.png"><img src="response_brightness.png"><img style="max-width:640px" src="response_focus_scan.gif"></section>"""
    (output / "index.html").write_text(page + "".join(cards) + "</html>", encoding="utf-8")


if __name__ == "__main__":
    main()
