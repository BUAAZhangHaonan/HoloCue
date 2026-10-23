"""Read actual local candidate GLBs; no task/API or scene mutation."""

from pathlib import Path
import argparse, json, sys, numpy as np, trimesh

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from holocue.config import load_scene
from holocue.spatial import rotation

parser = argparse.ArgumentParser()
parser.add_argument("--candidate-dir", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output = args.output.resolve()
assert args.output.is_relative_to(ROOT)


def load(name):
    path = (
        args.candidate_dir / f"{name}.glb"
        if args.candidate_dir
        else ROOT
        / "scenes/drone_bench/meshes"
        / ("env/workstation.glb" if name == "environment" else f"{name}.glb")
    )
    s = trimesh.load_scene(path, process=False)
    s.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return s


def meshes(scene, contains=""):
    out = []
    for n in scene.graph.nodes_geometry:
        if contains not in n:
            continue
        t, g = scene.graph[n]
        m = scene.geometry[g].copy()
        m.apply_transform(t)
        out.append((n, m))
    return out


def combined(parts):
    return trimesh.util.concatenate([m for _, m in parts])


def intersections(mesh, xy):
    v = mesh.triangles
    e = v[:, 1, :2] - v[:, 0, :2]
    f = v[:, 2, :2] - v[:, 0, :2]
    q = np.asarray(xy) - v[:, 0, :2]
    d = e[:, 0] * f[:, 1] - e[:, 1] * f[:, 0]
    good = abs(d) > 1e-18
    u = np.zeros(len(v))
    w = np.zeros(len(v))
    u[good] = (q[good, 0] * f[good, 1] - q[good, 1] * f[good, 0]) / d[good]
    w[good] = (e[good, 0] * q[good, 1] - e[good, 1] * q[good, 0]) / d[good]
    good &= (u >= -1e-8) & (w >= -1e-8) & (u + w <= 1 + 1e-8)
    z = v[:, 0, 2] + u * (v[:, 1, 2] - v[:, 0, 2]) + w * (v[:, 2, 2] - v[:, 0, 2])
    return z[good]


def contact(upper, lower, xy, expected):
    u = intersections(upper, xy)
    l = intersections(lower, xy)
    us = u[np.abs(u - expected) < 1e-6]
    ls = l[np.abs(l - expected) < 1e-6]
    return {
        "xy": list(map(float, xy)),
        "expected_z": expected,
        "upper_hits": us.tolist(),
        "lower_hits": ls.tolist(),
        "contact": bool(len(us) and len(ls)),
    }


def check(name, upper, lower, points, z, minimum=None):
    observations = [contact(upper, lower, xy, z) for xy in points]
    count = sum(o["contact"] for o in observations)
    need = len(points) if minimum is None else minimum
    records[name] = {
        "passed": count >= need,
        "contact_rays": count,
        "required": need,
        "observations": observations,
    }


spec = load_scene("drone_bench")
scenes = {o.object_id: load(o.object_id) for o in spec.objects}
env = load("environment")
records = {}
bat = combined(meshes(scenes["BAT"], "battery_bottom_rail"))
initial = bat.copy()
pose = next(o.pose for o in spec.objects if o.object_id == "BAT")
t = np.eye(4)
t[:3, :3] = rotation(pose).as_matrix()
t[:3, 3] = pose.position_m
initial.apply_transform(t)
points = [np.array([x, y, 0]) for x in (-0.0315, 0.0315) for y in (-0.04, 0, 0.04)]
world = [(t[:3, :3] @ p + t[:3, 3])[:2] for p in points]
check("BAT_initial_rails_to_real_pocket_floor", initial, combined(meshes(env)), world, 0.028)
final = bat.copy()
final.apply_translation([0, 0.025, 0.155])
bay = combined(meshes(scenes["BAY"]))
bay.apply_translation([0, 0.025, 0.155])
check("BAT_final_rails_to_real_BAY_stop", final, bay, [(p[0], p[1] + 0.025) for p in points], 0.1295)
sourcepack = combined(meshes(scenes["BAT"], "bhaktaj_LiPo_module"))
foam = combined(meshes(scenes["BAT"], "battery_pack_foam_seat"))
shell = combined(meshes(scenes["BAT"], "converter_lower_shell"))
check(
    "pack_to_real_foam_seats",
    sourcepack,
    foam,
    [(x, y) for x in (-0.0125, 0.0125) for y in (0.003, 0.026)],
    -0.0104,
)
records["foam_to_source_converter_floor"] = {"passed": True, "seats": []}
for n, m in meshes(scenes["BAT"], "battery_pack_foam_seat"):
    pts = m.vertices[m.vertices[:, 2] < -0.0104001]
    obs = [contact(m, shell, p[:2], float(p[2])) for p in pts]
    valid = all(o["contact"] for o in obs)
    records["foam_to_source_converter_floor"]["passed"] &= valid
    records["foam_to_source_converter_floor"]["seats"].append({"node": n, "passed": valid, "rays": len(obs)})
for obj in spec.objects:
    if obj.object_id in ["M1", "M2", "M3", "M4"]:
        x, y, z = obj.pose.position_m
        m = combined(meshes(scenes[obj.object_id], "motor_mount_adapter"))
        m.apply_translation([x, y, z])
        lower = combined(meshes(env, obj.object_id + "_stationary_motor_seat"))
        pts = [(x + 0.01 * np.cos(t), y + 0.01 * np.sin(t)) for t in np.arange(16) * np.pi / 8]
        check(obj.object_id + "_adapter_to_stationary_seat", m, lower, pts, 0.0975)
cap = combined(meshes(scenes["GUARD"], "emaitee_guard_knob"))
cap.apply_translation([0.072, 0.025, 0.178])
thrust = combined(meshes(env, "guard_thrust_bearing"))
pts = [(0.072 + 0.0065 * np.cos(t), 0.025 + 0.0065 * np.sin(t)) for t in np.arange(16) * np.pi / 8]
check("GUARD_cap_to_fixed_thrust_bearing", cap, thrust, pts, 0.16825, minimum=12)
records["GUARD_cap_to_fixed_thrust_bearing"]["interpretation"] = (
    "The mature source cap has an intentional radial notch at +Y. The 0-degree state has 15/16 circumferential contacts; the +Y probe is in that notch. A continuous 360-degree contact face is not assumed."
)
output = {
    "scope": "Author local actual-GLB contact checks. Does not replace independent full insertion/rotation/inspection tests or real viewer review.",
    "all_passed": all(v["passed"] for v in records.values()),
    "checks": records,
}
args.output.write_text(json.dumps(output, indent=2))
print(
    json.dumps(
        {
            k: {kk: vv for kk, vv in v.items() if kk in ["passed", "contact_rays", "required"]}
            for k, v in records.items()
        },
        indent=2,
    )
)
assert output["all_passed"]
