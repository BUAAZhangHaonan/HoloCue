"""The completed marker must contact real soil, not float above its anchor."""

import numpy as np
import pytest
from holocue.config import load_scene
from holocue.spatial import mating_goal, transform_points
from test_asset_reconstruction import meshes, triangles, vertical_hits


def test_completed_flag_contacts_exported_pit_floor_away_from_bone():
    spec = load_scene("dig_site")
    flag = next(obj for obj in spec.objects if obj.object_id == "FLAG")
    bone = next(obj for obj in spec.objects if obj.object_id == "BONE")
    goal = mating_goal(flag, bone, bone.pose, "assemble")
    flag_triangles = triangles(meshes(spec, flag, goal))
    bone_triangles = triangles(meshes(spec, bone))
    soil = np.concatenate([triangles(meshes(spec, prop)) for prop in spec.environment])
    tip = transform_points(goal, np.asarray([flag.interaction.mating_pose.position_m]))[0]
    np.testing.assert_allclose(tip, [0.32, 0.02, -0.35], atol=1e-8)
    assert flag_triangles[:, :, 2].min() == pytest.approx(tip[2], abs=0.00075)
    # Sample real soil triangles at and around the tip. A global floor AABB
    # cannot establish contact once excavation terrain has surface relief.
    for dx, dy in ((0, 0), (-0.001, 0), (0.001, 0), (0, -0.001), (0, 0.001)):
        heights = vertical_hits(soil, tip[:2] + [dx, dy])
        assert len(heights), "Marker tip has no actual soil below it"
        assert heights.max() == pytest.approx(tip[2], abs=0.00075)
    assert flag_triangles[:, :, 0].min() > bone_triangles[:, :, 0].max(), (
        "Marker overlaps the recorded remains"
    )
