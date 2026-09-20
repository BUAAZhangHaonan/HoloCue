"""Actual dive meshes: flat boot seats, grounded frame, and unobstructed labels."""
import json
import hashlib
from pathlib import Path

import numpy as np
import pytest
import trimesh

from holocue import camera
from holocue.assets import load_asset, world_scene
from holocue.config import load_scene, root
from holocue.modeling import make_environment, make_object
from holocue.models import SceneObject
from holocue.spatial import matrix, mating_goal, transform_points


def parts(scene, suffix):
    result = []
    for node in scene.graph.nodes_geometry:
        if str(node).endswith('_' + suffix):
            transform, name = scene.graph[node]
            mesh = scene.geometry[name].copy()
            mesh.apply_transform(transform)
            result.append(mesh)
    return result


def first_hit_distance(triangles, origin, direction):
    edge1 = triangles[:, 1] - triangles[:, 0]
    edge2 = triangles[:, 2] - triangles[:, 0]
    cross = np.cross(direction, edge2)
    determinant = np.einsum('ij,ij->i', edge1, cross)
    valid = np.abs(determinant) > 1e-12
    inverse = np.divide(1., determinant, out=np.zeros_like(determinant), where=valid)
    delta = origin - triangles[:, 0]
    u = np.einsum('ij,ij->i', delta, cross) * inverse
    q = np.cross(delta, edge1)
    v = (q @ direction) * inverse
    distance = np.einsum('ij,ij->i', edge2, q) * inverse
    hits = valid & (u >= -1e-9) & (v >= -1e-9) & (u+v <= 1+1e-9) & (distance > 0)
    return float(distance[hits].min()) if hits.any() else float('inf')


def inside(mesh, point):
    """Closed-surface solid-angle test on triangles, without an rtree index."""
    a, b, c = np.moveaxis(mesh.triangles-np.asarray(point), 1, 0)
    la, lb, lc = [np.linalg.norm(v, axis=1) for v in (a, b, c)]
    numerator = np.einsum('ij,ij->i', a, np.cross(b, c))
    denominator = (la*lb*lc + np.einsum('ij,ij->i', a, b)*lc
        + np.einsum('ij,ij->i', b, c)*la + np.einsum('ij,ij->i', c, a)*lb)
    return abs(np.sum(2*np.arctan2(numerator, denominator))) > 2*np.pi


@pytest.fixture(scope='module')
def candidate(tmp_path_factory):
    directory = tmp_path_factory.mktemp('dive_support')
    # Use the configured deployed root; immutable historical geometry lives in
    # the explicit SHA-checked fixture, not in this mutable resource mapping.
    spec = load_scene('dive_fillstation')
    assembly = make_environment(spec)
    path = directory / 'workstation.glb'
    assembly.save(path)
    exported = load_asset(str(path), spec.asset_axes)
    spec.environment[0].asset = str(path.relative_to(root()))
    stem = next(obj for obj in spec.objects if obj.object_id == 'STEM')
    stem_path = directory / 'STEM.glb'
    make_object(stem).save(stem_path)
    stem.asset = str(stem_path.relative_to(root()))
    return spec, assembly.scene, exported


@pytest.mark.parametrize('roundtrip', [False, True], ids=['generated', 'glb_roundtrip'])
def test_seats_contact_boot_faces_and_clear_lower_domes(candidate, roundtrip):
    spec, generated, exported = candidate
    env = exported if roundtrip else generated
    rack = parts(env, 'bottle_rack')[0]
    seats = sorted(parts(env, 'bottle_seat'), key=lambda m: m.centroid[0])
    bottles = sorted([o for o in spec.objects if o.recipe == 'cylinder'], key=lambda o: o.pose.position_m[0])
    assert len(seats) == len(bottles) == 3
    for seat, obj in zip(seats, bottles):
        local = load_asset(str(root()/obj.asset), spec.asset_axes).copy()
        local.apply_transform(matrix(obj.pose))
        boot, dome = parts(local, 'boot')[0], parts(local, 'base')[0]
        assert seat.bounds[0, 2] == pytest.approx(rack.bounds[1, 2], abs=1e-7)
        assert seat.bounds[1, 2] == pytest.approx(boot.bounds[0, 2], abs=1e-7)
        # All lower-dome vertices below the seating plane stay inside the real
        # polygonal bore; the seat leaves the 7.4 mm space below the bottle dome clear.
        low = dome.vertices[dome.vertices[:, 2] <= seat.bounds[1, 2]+1e-7]
        radial = np.linalg.norm(low[:, :2]-obj.pose.position_m[:2], axis=1)
        assert radial.max() < obj.size_m[0]*.46*np.cos(np.pi/48)-.002
        assert dome.bounds[0, 2] > rack.bounds[1, 2]
        # Multiple actual boot bottom triangles touch the seat's planar top.
        bottom = np.max(abs(boot.triangles[:, :, 2]-boot.bounds[0, 2]), axis=1) < 1e-7
        samples = boot.triangles_center[bottom]
        assert len(samples) >= 48
        _, distances, _ = trimesh.proximity.closest_point_naive(seat, samples)
        assert distances.max() < 1e-7


@pytest.mark.parametrize('roundtrip', [False, True], ids=['generated', 'glb_roundtrip'])
def test_grounded_frame_has_real_joints_to_rack_restraints_and_panel(candidate, roundtrip):
    spec, generated, exported = candidate
    env = exported if roundtrip else generated
    rack, panel = parts(env, 'bottle_rack')[0], parts(env, 'manifold_panel')[0]
    floor = parts(env, 'floor')[0]
    for name, expected in {'rack_foot': 4, 'panel_foot': 2, 'panel_post': 2,
            'rack_rear_tie': 2, 'restraint_panel_brace': 3,
            'gauge_panel_mount': 2, 'manifold_standoff': 2}.items():
        assert len(parts(env, name)) == expected, name
    for foot in parts(env, 'rack_foot') + parts(env, 'panel_foot'):
        assert foot.bounds[0, 2] == pytest.approx(floor.bounds[1, 2], abs=1e-7)
        topology = foot.copy()
        topology.merge_vertices(merge_norm=True, merge_tex=True)
        assert topology.is_watertight and topology.volume > 0
    for foot in parts(env, 'rack_foot'):
        point = foot.centroid.copy(); point[2] = foot.bounds[1, 2]
        _, distances, _ = trimesh.proximity.closest_point_naive(rack, [point])
        assert distances[0] < 1e-7
    for post in parts(env, 'panel_post'):
        x = post.centroid[0]
        assert inside(panel, [x, .77, .52])
        assert inside(post, [x, .77, .52])
        foot = min(parts(env, 'panel_foot'), key=lambda m: abs(m.centroid[0]-x))
        assert post.bounds[0, 2] == pytest.approx(foot.bounds[1, 2], abs=1e-7)
        bottom = np.max(abs(post.triangles[:, :, 2]-post.bounds[0, 2]), axis=1) < 1e-7
        contact_points = post.triangles_center[bottom]
        assert len(contact_points) >= 40
        _, distances, _ = trimesh.proximity.closest_point_naive(foot, contact_points)
        assert distances.max() < 1e-7
    for tie in parts(env, 'rack_rear_tie'):
        x = tie.centroid[0]
        assert inside(rack, [x, .24, .13]) and inside(tie, [x, .24, .13])
        post = min(parts(env, 'panel_post'), key=lambda m: abs(m.centroid[0]-x))
        assert inside(post, [x, .76, .13]) and inside(tie, [x, .76, .13])
    for brace in parts(env, 'restraint_panel_brace'):
        x = brace.centroid[0]
        short = min(parts(env, 'restraint_bracket'), key=lambda m: abs(m.centroid[0]-x))
        assert inside(short, [x, .365, .441]) and inside(brace, [x, .365, .441])
        point = [x, .730, .44+(.730-.36)*(.10/.375)]
        assert inside(panel, point) and inside(brace, point)
    for mount in parts(env, 'gauge_panel_mount'):
        point = [mount.centroid[0], .724, 1.515]
        assert inside(panel, point) and inside(mount, point)
        gauge = next(o for o in spec.objects if o.object_id == 'GAUGES')
        gauge_mesh = load_asset(str(root()/gauge.asset), spec.asset_axes).copy()
        gauge_mesh.apply_transform(matrix(gauge.pose))
        point = [mount.centroid[0], .697, 1.515]
        assert inside(parts(gauge_mesh, 'panel')[0], point) and inside(mount, point)
    for mount in parts(env, 'manifold_standoff'):
        point = [mount.centroid[0], .73, 1.25]
        assert inside(panel, point) and inside(mount, point)
        point = [mount.centroid[0], .630, 1.25]
        assert inside(parts(env, 'manifold')[0], point) and inside(mount, point)


@pytest.mark.parametrize('aspect', [.72, .97, 1.276, 16/9])
@pytest.mark.parametrize('installed', [False, True], ids=['initial', 'qrc_installed'])
def test_bottle3_front_label_and_body_have_clear_detail_sightlines(candidate, aspect, installed):
    spec, _, _ = candidate
    obj = next(o for o in spec.objects if o.object_id == 'BOTTLE3')
    local = load_asset(str(root()/obj.asset), spec.asset_axes)
    position, look, up = camera.detail_view(obj, obj.pose, local.bounds,
        np.asarray(spec.camera_position_m)-spec.camera_look_at_m, aspect=aspect)
    points = transform_points(obj.pose, camera.corners(local.bounds))
    projected, _ = camera.project(points, position, look, aspect=aspect, up=up)
    assert np.abs(projected).max() <= .860001
    poses = {}
    if installed:
        connector = next(o for o in spec.objects if o.object_id == 'QRC')
        valve = next(o for o in spec.objects if o.object_id == 'VALVE')
        poses['QRC'] = mating_goal(connector, valve, valve.pose, 'insert')
    world = world_scene(root(), spec, poses).to_geometry()
    # Fifteen label points cover its corners/edges/interior; 25 true front
    # body points cover five heights on either side and below/above the label.
    label = np.array([(x, -.19*.493, z) for x in np.linspace(-.19*.75/2, .19*.75/2, 5)
                      for z in np.linspace(-.74*.15/2, .74*.15/2, 3)])
    body = parts(local, 'bottle_body')[0]
    samples = []
    for x in (-.085, -.055, 0., .055, .085):
        for z in (-.26, -.20, .10, .19, .24):
            origin = np.array([x, -.2, z])
            distance = first_hit_distance(body.triangles, origin, np.array([0., 1., 0.]))
            assert np.isfinite(distance)
            samples.append(origin + np.array([0., distance, 0.]))
    for point in transform_points(obj.pose, np.concatenate([label, samples])):
        delta = point-position
        length = np.linalg.norm(delta)
        distance = first_hit_distance(world.triangles, np.asarray(position), delta/length)
        assert distance >= length-1e-6, 'An actual scene triangle hides the front label/body sample'


def test_original_environment_meshes_and_task_contract_are_unchanged(candidate):
    spec, _, env = candidate
    original = load_scene('dive_fillstation')
    original_env = load_asset(str(root()/original.environment[0].asset), original.asset_axes)
    for node in original_env.graph.nodes_geometry:
        old_transform, old_name = original_env.graph[node]
        transform, name = env.graph[node]
        # The independent immutable valve-seat fixture constrains these exact
        # two changed nodes, including preserved surfaces/materials and joints.
        if node not in {'dive_fillstation_environment/0009_manifold',
                        'dive_fillstation_environment/0016_tube'}:
            np.testing.assert_array_equal(env.geometry[name].vertices, original_env.geometry[old_name].vertices)
            np.testing.assert_array_equal(env.geometry[name].faces, original_env.geometry[old_name].faces)
        np.testing.assert_array_equal(transform, old_transform)
        for attribute in ('name', 'baseColorFactor', 'metallicFactor', 'roughnessFactor', 'doubleSided'):
            np.testing.assert_array_equal(getattr(env.geometry[name].visual.material, attribute),
                                          getattr(original_env.geometry[old_name].visual.material, attribute))
    assert spec.task_contract == original.task_contract
    for obj, before in zip(spec.objects, original.objects):
        after_data, before_data = obj.model_dump(), before.model_dump()
        if obj.object_id == 'STEM':
            # Only the private test asset path differs; deployment keeps the
            # declared STEM resource path while replacing its generated GLB.
            assert Path(obj.asset).name == 'STEM.glb'
            after_data['asset'] = before_data['asset']
        after_data['interaction'].pop('detail_direction_local')
        before_data['interaction'].pop('detail_direction_local')
        assert after_data == before_data


@pytest.mark.parametrize('roundtrip', [False, True], ids=['generated', 'glb_roundtrip'])
def test_stem_handle_and_retaining_bolt_are_connected_without_changing_details(candidate, roundtrip):
    spec, _, _ = candidate
    stem = next(obj for obj in spec.objects if obj.object_id == 'STEM')
    scene = load_asset(str(root()/stem.asset), spec.asset_axes) if roundtrip else make_object(stem).scene
    fixture = Path(__file__).parent/'fixtures/dive_fillstation'
    old_asset = fixture/'STEM_before_axial_clearance.glb'
    old_contract = fixture/'STEM_before_axial_clearance.json'
    assert hashlib.sha256(old_asset.read_bytes()).hexdigest() == 'f0166005d4b1e490320957e6e76034f25e32a44546f4419e0ce33f2d61a5edc2'
    assert hashlib.sha256(old_contract.read_bytes()).hexdigest() == '4ad01850c4e4cf35472d425bf9143bbffad4ed004be38d5977e6dadc8f0c19a0'
    reference = json.loads(old_contract.read_text(encoding='utf-8'))
    original = SceneObject.model_validate(reference['object'])
    assert reference['asset_axes'] == spec.asset_axes
    old_scene = load_asset(str(old_asset), reference['asset_axes'])
    for name in ('spindle', 'handle', 'retaining_bolt'):
        assert len(parts(scene, name)) == 1
        topology = parts(scene, name)[0].copy()
        topology.merge_vertices(merge_norm=True, merge_tex=True)
        assert topology.is_watertight and topology.is_winding_consistent and topology.volume > 0
    spindle, handle, bolt = [parts(scene, name)[0] for name in ('spindle', 'handle', 'retaining_bolt')]
    shift = np.array([0., -.0476, 0.])
    for name in ('handle', 'retaining_bolt'):
        before, after = parts(old_scene, name)[0], parts(scene, name)[0]
        np.testing.assert_array_equal(after.faces, before.faces)
        np.testing.assert_allclose(after.vertices, before.vertices+shift, atol=1e-7)
        assert after.visual.material.name == before.visual.material.name
    assert spindle.bounds[1, 1] == pytest.approx(.016, abs=1e-7)
    assert spindle.bounds[0, 1] == pytest.approx(-.068, abs=1e-7)
    np.testing.assert_allclose(spindle.bounds[:, [0, 2]], [[-.016, -.016], [.016, .016]], atol=1e-7)
    assert inside(spindle, [0., -.063, 0.]) and inside(handle, [0., -.063, 0.])
    assert inside(bolt, [0., -.0748, 0.]) and inside(handle, [0., -.0748, 0.])
    # Keep the historical attachment end fixed at the manifold side.
    np.testing.assert_allclose(stem.pose.position_m, original.pose.position_m)
    assert stem.interaction == original.interaction
