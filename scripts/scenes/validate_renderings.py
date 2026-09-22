"""Render every scene and its real inspection surface using the VTK CPU backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from holocue import camera
from holocue.assets import load_asset, world_scene, resource
from holocue.config import root, list_scenes, load_scene
from holocue.render_validation import render
from holocue.spatial import transform_points


def caption(image, text):
    out = Image.new("RGB", (image.width, image.height + 55), (239, 243, 246))
    out.paste(image, (0, 55))
    draw = ImageDraw.Draw(out)
    font = ImageFont.truetype("DejaVuSans.ttf", 24)
    draw.text((24, 16), text, font=font, fill=(39, 58, 75))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", nargs="*")
    parser.add_argument("--out", default="runs/simulation/visual")
    args = parser.parse_args()
    output = root() / args.out
    output.mkdir(parents=True, exist_ok=True)
    selected = args.scenes or [x["scene_id"] for x in list_scenes()]
    rows = []
    covers = []
    for sid in selected:
        spec = load_scene(sid)
        full = world_scene(root(), spec)
        points = []
        for obj in spec.objects:
            asset = load_asset(str(resource(root(), obj.asset)), spec.asset_axes)
            points.extend(transform_points(obj.pose, camera.corners(asset.bounds)))
        direction = np.asarray(spec.camera_position_m) - spec.camera_look_at_m
        framing = camera.workspace_points(spec, points)
        pos, look = camera.fit(framing, direction, aspect=1280 / 900)
        ndc, depth = camera.project(np.asarray(points), pos, look, aspect=1280 / 900)
        if np.abs(ndc).max() > 1:
            raise RuntimeError(f"{sid} contains out-of-frame task geometry")
        image = caption(render(full, pos, look), sid + "   |   workspace")
        image.save(output / f"{sid}_overview.png")
        covers.append((sid, image))
        front, frontlook = camera.fit(framing, (0, -1, 0.40), aspect=1280 / 900)
        caption(render(full, front, frontlook), sid + "   |   front").save(output / f"{sid}_front.png")
        step = spec.task_contract.ordered_steps[0]
        active = next(o for o in spec.objects if o.object_id == step.target_id)
        active_asset = load_asset(str(resource(root(), active.asset)), spec.asset_axes)
        dp, dl, du = camera.detail_view(
            active, active.pose, active_asset.bounds, direction, step.action, aspect=1280 / 900
        )
        caption(render(full, dp, dl, up=du), sid + "   |   " + active.object_id + " task detail").save(
            output / f"{sid}_detail.png"
        )
        focus = next(o for o in spec.objects if o.object_id == spec.task_contract.interrupt_target)
        asset = load_asset(str(resource(root(), focus.asset)), spec.asset_axes).copy()
        from holocue.spatial import matrix

        asset.apply_transform(matrix(focus.pose))
        ip, il, up = camera.inspect_view(focus, focus.pose, aspect=1280 / 900)
        caption(render(asset, ip, il, up=up), sid + "   |   " + focus.object_id + " inspection").save(
            output / f"{sid}_inspection.png"
        )
        entry = {
            "scene_id": sid,
            "objects": len(spec.objects),
            "frustum_max_abs_ndc": float(np.abs(ndc).max()),
            "depth_range_m": [float(depth.min()), float(depth.max())],
            "inspection_target": focus.object_id,
            "renderer": "VTK OSMesa llvmpipe CPU",
            "detail_target": active.object_id,
            "detail": f"{sid}_detail.png",
            "overview": f"{sid}_overview.png",
            "inspection": f"{sid}_inspection.png",
        }
        rows.append(entry)
        output.joinpath(f"{sid}_render.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
        print(sid, "rendered", flush=True)
    rows = [json.loads(p.read_text()) for p in sorted(output.glob("*_render.json"))]
    output.joinpath("render_report.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    covers = [(row["scene_id"], Image.open(output / row["overview"])) for row in rows]
    contact = Image.new("RGB", (1440, math_rows(len(covers)) * 380), (239, 243, 246))
    for index, (_, image) in enumerate(covers):
        image.thumbnail((480, 375))
        contact.paste(image, ((index % 3) * 480, (index // 3) * 380))
    contact.save(output / "twelve_scenes.png")


def math_rows(n):
    return (n + 2) // 3


if __name__ == "__main__":
    main()
