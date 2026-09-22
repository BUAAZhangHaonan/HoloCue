"""Actual mesh witnesses and the unchanged declared motion audit protocol."""

import hashlib, json
import numpy as np
import trimesh, vtk
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy
from holocue.assets import load_asset, resource
from holocue.config import root, load_policy
from holocue.models import CueSemantic, Decision, Session, Pose
from holocue.projection import packet
from holocue.render_validation import polydata
from holocue.spatial import matrix, trajectory
from holocue.state import apply_decision
from scripts.tests.audit_geometry import parts


def mesh_map(scene, pose=None):
    result = {}
    for node in scene.graph.nodes_geometry:
        tr, gn = scene.graph[node]
        m = scene.geometry[gn].copy()
        m.apply_transform(tr if pose is None else matrix(pose) @ tr)
        result[str(node)] = m
    return result


def material(mesh):
    m = mesh.visual.material
    result = {
        k: getattr(m, k, None)
        for k in ("name", "baseColorFactor", "metallicFactor", "roughnessFactor", "doubleSided", "alphaMode")
    }
    for key, val in list(result.items()):
        if isinstance(val, np.ndarray):
            result[key] = val.tolist()
    texture = getattr(m, "baseColorTexture", None)
    result["texture_sha256"] = (
        None if texture is None else hashlib.sha256(np.asarray(texture).tobytes()).hexdigest()
    )
    return result


def fingerprint(mesh):
    h = hashlib.sha256()
    for arr in (mesh.vertices, mesh.faces, mesh.vertex_normals, mesh.visual.uv):
        if arr is None:
            h.update(b"None")
            continue
        aa = np.asarray(arr)
        h.update(str(aa.shape).encode())
        h.update(aa.tobytes())
    h.update(json.dumps(material(mesh), sort_keys=True).encode())
    return h.hexdigest()


def vertical_hit(mesh, xy, highest=True):
    tris = mesh.triangles
    a = tris[:, 0, :2]
    u = tris[:, 1, :2] - a
    v = tris[:, 2, :2] - a
    w = np.asarray(xy) - a
    det = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    good = np.abs(det) > 1e-15
    s = np.divide(w[:, 0] * v[:, 1] - w[:, 1] * v[:, 0], det, out=np.zeros_like(det), where=good)
    t = np.divide(u[:, 0] * w[:, 1] - u[:, 1] * w[:, 0], det, out=np.zeros_like(det), where=good)
    hit = np.flatnonzero(good & (s >= -1e-8) & (t >= -1e-8) & (s + t <= 1 + 1e-8))
    if not len(hit):
        return None
    zs = tris[:, 0, 2] + s * (tris[:, 1, 2] - tris[:, 0, 2]) + t * (tris[:, 2, 2] - tris[:, 0, 2])
    i = int(hit[np.argmax(zs[hit]) if highest else np.argmin(zs[hit])])
    return {"z": float(zs[i]), "triangle_index": i, "triangle": tris[i].tolist()}


def bottom_contacts(upper, lower):
    z = float(upper.vertices[:, 2].min())
    indices = np.flatnonzero(np.max(np.abs(upper.triangles[:, :, 2] - z), axis=1) < 1e-7)
    assert len(indices)
    rows = []
    for i in indices:
        p = upper.triangles[i].mean(axis=0)
        hit = vertical_hit(lower, p[:2])
        if hit is not None and abs(float(p[2]) - hit["z"]) < 1e-6:
            rows.append(
                {
                    "upper_triangle_index": int(i),
                    "upper_triangle": upper.triangles[i].tolist(),
                    "point": p.tolist(),
                    "lower": hit,
                    "gap_m": float(p[2]) - hit["z"],
                }
            )
    assert len(rows) >= 8, ("insufficient actual bearing triangles", len(rows))
    return {
        "bearing_triangle_count": len(rows),
        "witnesses": rows[:8],
        "maximum_contact_gap_m": max(abs(r["gap_m"]) for r in rows),
    }


def ray_hits(mesh, origin, direction):
    tri = mesh.triangles
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    cross = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, cross)
    valid = np.abs(det) > 1e-13
    inv = np.divide(1, det, out=np.zeros_like(det), where=valid)
    delta = np.asarray(origin) - tri[:, 0]
    u = np.einsum("ij,ij->i", delta, cross) * inv
    q = np.cross(delta, e1)
    v = (q @ direction) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hits = np.flatnonzero(valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1 + 1e-8) & (t > 1e-9))
    hits = hits[np.argsort(t[hits])]
    result = []
    for i in hits:
        if result and abs(result[-1]["distance_m"] - float(t[i])) < 1e-8:
            continue
        result.append(
            {
                "distance_m": float(t[i]),
                "triangle_index": int(i),
                "triangle": tri[i].tolist(),
                "point": (np.asarray(origin) + t[i] * direction).tolist(),
            }
        )
    return result


def distances(target, points):
    target = target.copy()
    target.process(validate=True)
    assert target.is_watertight and target.is_winding_consistent
    field = vtk.vtkImplicitPolyDataDistance()
    field.SetInput(polydata(target))
    values = vtk.vtkDoubleArray()
    field.EvaluateFunction(numpy_to_vtk(np.ascontiguousarray(points), deep=True), values)
    return vtk_to_numpy(values).copy()


def cavity_evidence(stock, moving, centre, seat_z, stock_bottom_z, stock_top_z, moving_radius, hole_radius):
    centre = np.asarray(centre)
    seat = vertical_hit(stock, centre[:2])
    bottom = vertical_hit(stock, centre[:2], False)
    assert abs(seat["z"] - seat_z) < 1e-7 and abs(bottom["z"] - stock_bottom_z) < 1e-7
    assert abs(stock.vertices[:, 2].max() - stock_top_z) < 1e-7
    radial = []
    mid = (seat_z + stock_top_z) / 2
    for angle in np.linspace(0, 2 * np.pi, 80, endpoint=False):
        direction = np.array([np.cos(angle), np.sin(angle), 0.0])
        hit = ray_hits(stock, [*centre[:2], mid], direction)
        assert hit
        assert hole_radius - 0.00015 <= hit[0]["distance_m"] <= hole_radius + 1e-7
        assert hit[0]["distance_m"] - moving_radius > 0.0001
        radial.append(
            {
                "angle_rad": float(angle),
                "wall": hit[0],
                "radial_clearance_m": hit[0]["distance_m"] - moving_radius,
                "outer_wall_distance_m": hit[1]["distance_m"] if len(hit) > 1 else None,
            }
        )
    witness = bottom_contacts(moving, stock)
    solid = stock.copy()
    solid.process(validate=True)
    assert solid.is_watertight and solid.is_winding_consistent and solid.volume > 0
    return {
        "seat": seat,
        "stock_bottom": bottom,
        "residual_floor_thickness_m": seat["z"] - bottom["z"],
        "bearing": witness,
        "radial_minimum_clearance_m": min(r["radial_clearance_m"] for r in radial),
        "radial_witnesses": radial,
        "closed_positive_volume_m3": float(solid.volume),
    }


def exterior_evidence(before, after, cuts):
    assert material(before) == material(after)
    np.testing.assert_allclose(before.bounds, after.bounds, atol=1e-7, rtol=0)
    rows = []
    for source, target in ((before, after), (after, before)):
        points = np.concatenate([source.vertices, source.triangles_center])
        keep = np.ones(len(points), bool)
        for centre, radius, floor in cuts:
            keep &= ~(
                (np.linalg.norm(points[:, :2] - np.asarray(centre)[:2], axis=1) < radius + 0.00015)
                & (points[:, 2] > floor - 1e-7)
            )
        assert keep.sum() > 100
        ds = distances(target, points[keep])
        maximum = float(np.abs(ds).max())
        assert maximum < 0.00005, maximum
        i = int(np.argmax(np.abs(ds)))
        rows.append(
            {
                "sample_count": int(keep.sum()),
                "maximum_surface_distance_m": maximum,
                "maximum_point": points[keep][i].tolist(),
            }
        )
    return {
        "bidirectional_unchanged_surface_samples": rows,
        "surface_tolerance_m": 0.00005,
        "same_bounds": True,
        "same_material": True,
    }


def latch_seat_evidence(
    stock, before, moving, centre, seat_z, stock_bottom_z, stock_top_z, moving_radius, hole_radius
):
    """The narrow latch stock has two intended side openings, not a closed bore."""
    centre = np.asarray(centre)
    seat = vertical_hit(stock, centre[:2])
    bottom = vertical_hit(stock, centre[:2], False)
    assert abs(seat["z"] - seat_z) < 1e-7 and abs(bottom["z"] - stock_bottom_z) < 1e-7
    assert abs(stock.vertices[:, 2].max() - stock_top_z) < 1e-7
    rays = []
    mid = (seat_z + stock_top_z) / 2
    for angle in np.linspace(0, 2 * np.pi, 80, endpoint=False):
        direction = np.array([np.cos(angle), np.sin(angle), 0.0])
        origin = [*centre[:2], mid]
        original = ray_hits(before, origin, direction)
        assert original
        hit = ray_hits(stock, origin, direction)
        if hit:
            assert hole_radius - 0.00015 <= hit[0]["distance_m"] <= hole_radius + 1e-7
            assert hit[0]["distance_m"] - moving_radius > 0.0001
            rays.append(
                {
                    "angle_rad": float(angle),
                    "kind": "recess_wall",
                    "wall": hit[0],
                    "radial_clearance_m": hit[0]["distance_m"] - moving_radius,
                    "original_outer_surface": original[-1],
                }
            )
        else:
            assert original[-1]["distance_m"] < hole_radius + 0.00015
            rays.append(
                {
                    "angle_rad": float(angle),
                    "kind": "open_side",
                    "original_outer_surface": original[-1],
                    "candidate_intersection_count": 0,
                }
            )
    assert sum(r["kind"] == "open_side" for r in rays) >= 2
    assert sum(r["kind"] == "recess_wall" for r in rays) >= 2
    solid = stock.copy()
    solid.process(validate=True)
    assert solid.is_watertight and solid.is_winding_consistent and solid.volume > 0
    return {
        "seat": seat,
        "stock_bottom": bottom,
        "residual_floor_thickness_m": seat["z"] - bottom["z"],
        "bearing": bottom_contacts(moving, stock),
        "radial_witnesses": rays,
        "closed_positive_volume_m3": float(solid.volume),
    }


def sweep(spec, source_overrides=None):
    source_overrides = {} if source_overrides is None else source_overrides
    cues = [
        CueSemantic(
            target_id=s.target_id,
            action=s.action,
            reference_id=s.reference_id,
            angle_deg=s.angle_deg,
            cue_type="ring_arrow" if s.action == "rotate" else "ghost_motion",
            task_role="current" if i == 0 else "next",
            priority=5,
            depth_requirement=s.depth_requirement,
            instruction="Declared task geometry audit",
        )
        for i, s in enumerate(spec.task_contract.ordered_steps)
    ]
    state = apply_decision(
        Session(
            session_id="panel-optical-mounts", scene_id=spec.scene_id, backend_mode="geometry_validation"
        ),
        Decision(operation="replace", assistant_message="Evaluate declared trajectories", cues=cues),
        spec,
    )
    objects = {o.object_id: o for o in spec.objects}
    rows = []
    for step in spec.task_contract.ordered_steps:
        display = packet(state, spec, load_policy())
        cue = next(c for c in display.cues if c.task_role == "current")
        assert cue.target_id == step.target_id
        source = objects[step.target_id]
        if step.action in ("insert", "assemble", "rotate"):
            scene = load_asset(
                str(resource(root(), source_overrides.get(source.object_id, source.asset))), spec.asset_axes
            )
            mesh = scene.to_geometry()
            points, face_indices = trimesh.sample.sample_surface(mesh, 1536, seed=4701)
            source_parts = []
            reassembled = []
            for node in scene.graph.nodes_geometry:
                tr, gn = scene.graph[node]
                m = scene.geometry[gn].copy()
                m.apply_transform(tr)
                reassembled.append(m)
                source_parts.extend([str(node)] * len(m.faces))
            combined = trimesh.util.concatenate(reassembled)
            np.testing.assert_array_equal(combined.vertices, mesh.vertices)
            np.testing.assert_array_equal(combined.faces, mesh.faces)
            part_names = np.asarray(source_parts)[face_indices]
            static = [
                o.model_copy(update={"pose": display.object_poses[o.object_id]}, deep=True)
                for o in spec.objects
                if o.object_id != source.object_id
            ]
            obstacles, coverage = parts(spec, static + spec.environment)
            hits = []
            poses = []
            for frame, t in enumerate(np.linspace(0, source.interaction.duration_s, 41)):
                pose = trajectory(cue, float(t))
                poses.append(pose.model_dump(mode="json"))
                world = trimesh.transform_points(points, matrix(pose))
                lo, hi = world.min(axis=0), world.max(axis=0)
                for oid, name, bounds, field in obstacles:
                    if np.any(lo > bounds[1]) or np.any(hi < bounds[0]):
                        continue
                    select = ((world > bounds[0] + 0.00075) & (world < bounds[1] - 0.00075)).all(axis=1)
                    if not select.any():
                        continue
                    values = vtk.vtkDoubleArray()
                    field.EvaluateFunction(
                        numpy_to_vtk(np.ascontiguousarray(world[select]), deep=True), values
                    )
                    ds = vtk_to_numpy(values)
                    hit = ds < -0.00075
                    if hit.any():
                        names, counts = np.unique(part_names[select][hit], return_counts=True)
                        hits.append(
                            {
                                "frame": frame,
                                "elapsed_s": float(t),
                                "obstacle": oid,
                                "part": name,
                                "points": int(hit.sum()),
                                "max_depth_m": float(-ds.min()),
                                "source_parts": {n: int(c) for n, c in zip(names, counts)},
                                "source_part_max_depth_m": {
                                    n: float(-ds[hit][part_names[select][hit] == n].min()) for n in names
                                },
                                "source_face_indices": face_indices[select][hit].tolist(),
                            }
                        )
            rows.append(
                {
                    "scene_id": spec.scene_id,
                    "source_id": source.object_id,
                    "action": step.action,
                    "angle_deg": step.angle_deg,
                    "source_sample_sha256": hashlib.sha256(points.tobytes()).hexdigest(),
                    "sampled_surface_points": 1536,
                    "seed": 4701,
                    "trajectory_samples": 41,
                    "penetration_threshold_m": 0.00075,
                    "trajectory": poses,
                    "prior_completed": [t.semantic.model_dump(mode="json") for t in state.completed],
                    "object_poses": {k: v.model_dump(mode="json") for k, v in display.object_poses.items()},
                    "penetrations": hits,
                    "obstacle_coverage": coverage,
                    "passed": not hits and not any(c["status"] == "invalid_solid_topology" for c in coverage),
                }
            )
        state = apply_decision(
            state, Decision(operation="complete", assistant_message="Complete inspected step"), spec
        )
    return rows
