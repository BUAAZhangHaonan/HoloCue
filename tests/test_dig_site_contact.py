"""The completed marker must contact real soil, not float above its anchor."""
import numpy as np
import pytest
import trimesh

from holocue.assets import world_scene
from holocue.config import load_scene, root
from holocue.spatial import mating_goal


def test_completed_flag_contacts_exported_pit_floor_away_from_bone():
    spec = load_scene('dig_site')
    flag = next(obj for obj in spec.objects if obj.object_id == 'FLAG')
    bone = next(obj for obj in spec.objects if obj.object_id == 'BONE')
    goal = mating_goal(flag, bone, bone.pose, 'assemble')
    world = world_scene(root(), spec, {'FLAG': goal})
    pole_bounds = None
    floor_bounds = None
    bone_bounds = []
    for node in world.graph.nodes_geometry:
        transform, name = world.graph[node]
        vertices = trimesh.transform_points(world.geometry[name].vertices, transform)
        bounds = np.array([vertices.min(axis=0), vertices.max(axis=0)])
        if node.startswith('FLAG/') and node.endswith('_flagpole'):
            pole_bounds = bounds
        elif node.endswith('_pit_floor'):
            floor_bounds = bounds
        elif node.startswith('BONE/'):
            bone_bounds.append(bounds)
    assert pole_bounds is not None and floor_bounds is not None and bone_bounds
    # Keep the pole within the flat interior, beyond the rounded floor edges.
    assert np.all(pole_bounds[0, :2] > floor_bounds[0, :2] + .01)
    assert np.all(pole_bounds[1, :2] < floor_bounds[1, :2] - .01)
    assert pole_bounds[0, 2] == pytest.approx(floor_bounds[1, 2], abs=.00075)
    bone_upper_x = max(bounds[1, 0] for bounds in bone_bounds)
    assert pole_bounds[0, 0] > bone_upper_x, 'Marker overlaps the recorded remains'
