"""Controlled native Viser lighting pairs using immutable real-session snapshots.

The production SceneRenderer loads the actual GLBs. This harness does not run or
alter a task: its input snapshots must come from the separate live-model audit.
It changes lighting through the official Python scene API, leaving each pair's
camera, poses, materials and guidance setting unchanged.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import threading
import time

import numpy as np
import msgpack
from playwright.sync_api import sync_playwright
from scipy.spatial.transform import Rotation
import trimesh
import viser
import zstandard

from holocue.config import load_scene, root
from holocue.models import DisplayPacket
from holocue.viewer_scene import SceneRenderer

JS = """() => {
const v=window.__viserMutable,s=v?.scene;if(!s)return null;
const meshes=[];s.traverse(o=>{if(o.isMesh&&o.name.includes('mirror_face'))meshes.push({name:o.name,matrixWorld:o.matrixWorld.toArray(),vertices:o.geometry.attributes.position.count,metalness:o.material.metalness,roughness:o.material.roughness,color:o.material.color.toArray()});});
return {environmentRotation:s.environmentRotation.toArray(),environmentIntensity:s.environmentIntensity,environment:{width:s.environment?.image?.width,height:s.environment?.image?.height,type:s.environment?.type,mapping:s.environment?.mapping,colorSpace:s.environment?.colorSpace},meshes,camera:{position:v.camera.position.toArray(),matrixWorld:v.camera.matrixWorld.toArray(),projectionMatrix:v.camera.projectionMatrix.toArray()},canvas:{width:v.canvas.width,height:v.canvas.height,opacity:v.canvas.style.opacity}};
}"""


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reflection(runtime, path):
    scene = trimesh.load_scene(path, process=False)
    node = next(n for n in scene.graph.nodes_geometry if "mirror_face" in n)
    mesh = scene.geometry[scene.graph[node][1]].copy()
    material = runtime["meshes"][0]
    assert len(mesh.vertices) == material["vertices"]
    mesh.apply_transform(np.asarray(material["matrixWorld"]).reshape(4, 4).T)
    eye = np.asarray(runtime["camera"]["position"]) - mesh.triangles_center
    eye /= np.linalg.norm(eye, axis=1)[:, None]
    indices = np.flatnonzero(np.einsum("ij,ij->i", mesh.face_normals, eye) > 0.85)
    normal = mesh.face_normals[indices]
    direction = 2 * np.einsum("ij,ij->i", eye[indices], normal)[:, None] * normal - eye[indices]
    rotation = Rotation.from_euler("XYZ", runtime["environmentRotation"][:3])
    local = rotation.inv().apply(direction)
    uv = np.column_stack(
        [np.arctan2(local[:, 2], local[:, 0]) / (2 * np.pi) + 0.5, np.arcsin(local[:, 1]) / np.pi + 0.5]
    )
    return {
        "front_triangles": indices.tolist(),
        "reflected_three_world": direction.tolist(),
        "environment_local_uv": uv.tolist(),
        "mapping_note": "Geometric direction estimate; native decoded HDR and actual rendered pixels are authoritative.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8783)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    spec = load_scene("optical_bench")
    initial = json.loads((args.live / "snapshots.json").read_text())[0]
    completed = json.loads((args.live / "completed_snapshots.json").read_text())[-1]
    assert initial["state"]["backend_mode"] == completed["state"]["backend_mode"] == "live"
    assert initial["state"]["session_id"] == completed["state"]["session_id"]
    server = viser.ViserServer(host="127.0.0.1", port=args.port)
    ready = threading.Event()
    renderers = []
    errors = []
    orientation = [(1.0, 0.0, 0.0, 0.0)]

    @server.on_client_connect
    def connected(client):
        client_spec = spec.model_copy(deep=True)
        client_spec.render_hints.environment_wxyz = orientation[0]
        renderers.append(SceneRenderer(client, client_spec))
        ready.set()

    rows = []
    environment_messages = []

    def received(payload):
        size = int.from_bytes(payload[:8], "little")
        compressed = int.from_bytes(payload[8:16], "little")
        messages = msgpack.unpackb(
            zstandard.ZstdDecompressor().decompress(payload[16 : 16 + compressed], max_output_size=size),
            raw=False,
            strict_map_key=False,
        )["messages"]
        for message in messages:
            if message.get("type") == "EnvironmentMapMessage":
                data = message["hdri_data"]
                sha = hashlib.sha256(data).hexdigest()
                (args.out / f"{sha}.jpg").write_bytes(data)
                environment_messages.append(
                    {
                        **{k: v for k, v in message.items() if k != "hdri_data"},
                        "hdri_sha256": sha,
                        "hdri_bytes": len(data),
                    }
                )

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
            )
            for state, snapshot in [("initial", initial), ("completed", completed)]:
                save(args.out / f"{state}_session.json", snapshot)
                pair = []
                for label, q in [
                    ("before", (1.0, 0.0, 0.0, 0.0)),
                    ("after", spec.render_hints.environment_wxyz),
                ]:
                    # Production chooses this constant at scene construction.
                    # Independent clients also prevent hot-update frame lag.
                    orientation[0] = q
                    ready.clear()
                    context = browser.new_context(viewport={"width": 1600, "height": 1000})
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("websocket", lambda ws: ws.on("framereceived", received))
                    page.goto(f"http://127.0.0.1:{args.port}", wait_until="networkidle")
                    page.get_by_role("checkbox", name="Dev Settings", exact=True).check()
                    page.get_by_role("combobox", name="Device Pixel Ratio", exact=True).click()
                    page.get_by_role("option", name="1.0", exact=True).click()
                    page.get_by_role("checkbox", name="Dev Settings", exact=True).uncheck()
                    if not ready.wait(30):
                        raise TimeoutError("Viser client did not connect")
                    renderer = renderers[-1]
                    renderer.guidance_enabled = False
                    renderer.update_packet(DisplayPacket.model_validate(snapshot["display"]))
                    renderer.packet = None
                    renderer.select_view("detail", "M")
                    renderer.client.flush()
                    page.wait_for_timeout(5000)
                    runtime = page.evaluate(JS)
                    assert runtime["environment"]["width"] == 1024 and runtime["environmentIntensity"] == 0.1
                    assert len(runtime["meshes"]) == 1
                    assert (
                        runtime["meshes"][0]["metalness"] == 0.95
                        and runtime["meshes"][0]["roughness"] == 0.08
                    )
                    runtime["configured_environment_wxyz"] = q
                    runtime["reflection"] = reflection(runtime, root() / "scenes/optical_bench/meshes/M.glb")
                    save(args.out / f"{state}_{label}.json", runtime)
                    page.screenshot(path=str(args.out / f"{state}_{label}.png"))
                    pair.append(runtime)
                    if state == "completed" and label == "after":
                        for oid in ("L1", "L2", "TARGET"):
                            renderer.select_view("detail", oid)
                            renderer.client.flush()
                            page.wait_for_timeout(2000)
                            page.screenshot(path=str(args.out / f"{oid}_after.png"))
                    context.close()
                for key in pair[0]["camera"]:
                    np.testing.assert_allclose(
                        pair[0]["camera"][key], pair[1]["camera"][key], atol=1e-7, rtol=0
                    )
                assert pair[0]["meshes"] == pair[1]["meshes"]
                rows.append(
                    {
                        "state": state,
                        "session_id": snapshot["state"]["session_id"],
                        "revision": snapshot["state"]["revision"],
                        "camera_and_materials_unchanged": True,
                    }
                )
            browser.close()
    finally:
        server.stop()
        save(
            args.out / "report.json",
            {
                "pairs": rows,
                "browser_errors": errors,
                "guidance_enabled": False,
                "environment_messages": environment_messages,
                "render_pixel_ratio": "1.0 via visible Viser setting",
                "visual_acceptance": "pending human/agent image inspection",
                "scope": "Native production SceneRenderer with recorded real-model states; separate from main Viewer UI workflow",
                "inputs": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [args.live / "snapshots.json", args.live / "completed_snapshots.json"]
                },
            },
        )
    assert len(rows) == 2 and not errors


if __name__ == "__main__":
    main()
