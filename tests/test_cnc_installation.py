"""Physical support and real mesh visibility of the CNC teaching controls."""

import numpy as np
import pytest
import trimesh
import vtk

from holocue import camera
from holocue.config import load_scene
from holocue.modeling import make_environment, make_object
from holocue.render_validation import polydata
from holocue.spatial import matrix


def world_parts(assembly, pose=None):
    result = {}
    for node in assembly.scene.graph.nodes_geometry:
        local, name = assembly.scene.graph[node]
        mesh = assembly.scene.geometry[name].copy()
        mesh.apply_transform(local if pose is None else matrix(pose) @ local)
        result[str(node)] = mesh
    return result


@pytest.fixture(scope="module")
def cnc():
    spec = load_scene("cnc_toolchange")
    objects = {o.object_id: world_parts(make_object(o), o.pose) for o in spec.objects}
    return spec, objects, world_parts(make_environment(spec))


def part(parts, suffix):
    matches = [mesh for name, mesh in parts.items() if name.endswith(suffix)]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize("oid", ["PANEL", "MODESWITCH"])
def test_controls_have_real_console_contact_and_clear_left_column(cnc, oid):
    _, objects, environment = cnc
    console = part(environment, "_control_console").bounds
    left = part(environment, "/0008_machine_side_column").bounds
    combined = trimesh.util.concatenate(list(objects[oid].values()))
    assert combined.bounds[1, 0] <= left[0, 0] - 0.0049
    assert abs(combined.bounds[1, 1] - console[0, 1]) < 1e-7
    contact_area = 0.0
    for mesh in objects[oid].values():
        triangles = mesh.triangles
        on_plane = np.abs(triangles[:, :, 1] - console[0, 1]).max(axis=1) < 1e-7
        # Stay inside the planar console front, excluding its rounded rim.
        supported = (
            (triangles[:, :, 0] > console[0, 0] + 0.006)
            & (triangles[:, :, 0] < console[1, 0] - 0.006)
            & (triangles[:, :, 2] > console[0, 2] + 0.006)
            & (triangles[:, :, 2] < console[1, 2] - 0.006)
        ).all(axis=1)
        contact_area += mesh.area_faces[on_plane & supported].sum()
    assert contact_area > 0.002


def test_magazine_mount_connects_hub_to_column_without_crossing_covers(cnc):
    _, objects, environment = cnc
    hub = part(objects["MAG"], "_hub").bounds
    disc = part(objects["MAG"], "_magazine_disc").bounds
    mount = part(environment, "_magazine_mount_standoff").bounds
    column = part(environment, "_machine_column").bounds
    spindle = part(environment, "_spindle_housing").bounds
    folds = [mesh.bounds for name, mesh in environment.items() if name.endswith("_way_cover_fold")]
    assert disc[1, 1] < min(b[0, 1] for b in folds)
    assert disc[0, 0] > spindle[1, 0] + 0.008
    assert np.isclose(mount[0, 1], hub[1, 1], atol=1e-7)
    assert np.isclose(mount[1, 1], column[0, 1], atol=1e-7)
    assert np.all(mount[0, [0, 2]] > column[0, [0, 2]] + 0.006)
    assert np.all(mount[1, [0, 2]] < column[1, [0, 2]] - 0.006)
    assert np.all(mount[0, [0, 2]] > hub[0, [0, 2]])
    assert np.all(mount[1, [0, 2]] < hub[1, [0, 2]])
    # Appending a mount must not renumber the established console/label nodes.
    assert "cnc_toolchange_environment/0043_control_console" in environment
    assert "cnc_toolchange_environment/label_44" in environment
    assert "cnc_toolchange_environment/0045_magazine_mount_standoff" in environment


def test_workspace_rays_reach_each_target_before_environment(cnc):
    spec, objects, environment = cnc
    meshes = []
    owners = []
    ends = []
    count = 0
    points = []
    for oid, parts in [*objects.items(), ("environment", environment)]:
        for mesh in parts.values():
            meshes.append(mesh)
            count += len(mesh.faces)
            owners.append(oid)
            ends.append(count)
        if oid != "environment":
            points.extend(camera.corners(trimesh.util.concatenate(list(parts.values())).bounds))
    position, _ = camera.fit(
        camera.workspace_points(spec, points),
        np.asarray(spec.camera_position_m) - spec.camera_look_at_m,
        aspect=1280 / 900,
    )
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(polydata(trimesh.util.concatenate(meshes)))
    locator.BuildLocator()
    cell = vtk.vtkGenericCell()
    for obj in spec.objects:
        target = np.array(obj.pose.position_m)
        direction = target - position
        endpoint = target + direction / np.linalg.norm(direction) * 0.001
        t = vtk.mutable(0.0)
        hit = [0.0, 0.0, 0.0]
        pcoords = [0.0, 0.0, 0.0]
        sub = vtk.mutable(0)
        cell_id = vtk.mutable(0)
        assert locator.IntersectWithLine(position, endpoint, 1e-9, t, hit, pcoords, sub, cell_id, cell), (
            obj.object_id
        )
        first = owners[int(np.searchsorted(ends, int(cell_id), side="right"))]
        assert first == obj.object_id, (obj.object_id, first)
