"""Actual exported infusion solids, including retained bores and source detail."""

import numpy as np
import pytest
import trimesh

from holocue.config import load_scene
from holocue.models import Pose
from panel_optical_geometry import ray_hits
from scripts.scenes.rebuild_infusion_assets import bag_source
from scripts.tests.audit_geometry import geometry_copy, parts
from test_asset_reconstruction import meshes


def object_parts(identifier):
    spec = load_scene("infusion_ward")
    obj = next(obj for obj in spec.objects if obj.object_id == identifier)
    return meshes(spec, obj, Pose())


def test_infusion_ward_all_actual_solids_are_covered():
    spec = load_scene("infusion_ward")
    _, coverage = parts(spec, [*spec.objects, *spec.environment])
    excluded = {row["part"] for row in coverage if row["status"] == "excluded_textured_label_surface"}
    assert excluded == {
        "PUMPCASSETTE/label_cassette_identification",
        "SLOT2/label_slot_id",
        "MONITOR/label_monitor_training_status",
    }
    assert len(coverage) == 92
    assert all(
        row["status"] in {"included_closed_solid", "excluded_textured_label_surface"} for row in coverage
    ), coverage
    assert sum(row["status"] == "included_closed_solid" for row in coverage) == 89


@pytest.mark.parametrize("identifier", ["BAG1", "BAG2"])
def test_infusion_ward_bag_retains_original_exterior_uvs_and_two_open_outlets(identifier):
    body = next(part for name, part in object_parts(identifier).items() if "ethan_cragun_water_bag" in name)
    source = bag_source()
    # The complete licensed outer film, not just its bounds, remains intact.
    np.testing.assert_allclose(body.triangles[: len(source.faces)], source.triangles, atol=2e-8, rtol=0)
    np.testing.assert_allclose(body.visual.uv[: len(source.vertices)], source.visual.uv, atol=1e-7, rtol=0)
    np.testing.assert_array_equal(
        np.asarray(body.visual.material.baseColorTexture), np.asarray(source.visual.material.baseColorTexture)
    )
    q = geometry_copy(source)
    counts = np.bincount(q.edges_unique_inverse)
    groups = trimesh.graph.connected_components(q.edges_unique[counts == 1])
    assert len(groups) == 2 and all(len(group) == 10 for group in groups)
    for group in groups:
        rim = q.vertices[group]
        center = rim.mean(axis=0)
        _, _, basis = np.linalg.svd(rim - center)
        axis = basis[-1]
        if axis[2] < 0:
            axis = -axis
        # A ray entering the centre cannot strike an outlet cap. Deeper in
        # the outlet, radial rays must see finite inner and outer film walls.
        hits = ray_hits(body, center - axis * 0.001, axis)
        assert not hits or hits[0]["distance_m"] > 0.002, (identifier, "capped bag outlet", hits[:1])
        for angle in np.linspace(0.11, 2 * np.pi + 0.11, 12, endpoint=False):
            radial = np.cos(angle) * basis[0] + np.sin(angle) * basis[1]
            hits = ray_hits(body, center + axis * 0.0006, radial)
            original = ray_hits(source, center + axis * 0.0006, radial)
            assert len(hits) >= 2, (identifier, "missing inner film", center, hits)
            inner, outer = hits[:2]
            assert original and inner["distance_m"] > 0.8 * original[0]["distance_m"]
            assert outer["distance_m"] == pytest.approx(original[0]["distance_m"], abs=2e-8)
            # The source outlet is folded and oblique; compare physical film
            # thickness normal to its face, not a grazing ray's path length.
            normal = source.face_normals[original[0]["triangle_index"]]
            thickness = (outer["distance_m"] - inner["distance_m"]) * abs(normal @ radial)
            assert thickness == pytest.approx(0.0001, abs=0.00002)


def test_infusion_ward_case_has_no_degenerate_t_junction_faces():
    case = next(
        part for name, part in object_parts("SLOT2").items() if "contec_source_open_receiver_case" in name
    )
    q = geometry_copy(case)
    cross = np.cross(q.triangles[:, 1] - q.triangles[:, 0], q.triangles[:, 2] - q.triangles[:, 0])
    assert len(q.faces) == 694
    assert np.all(np.linalg.norm(cross, axis=1) > 1e-15)
    assert q.is_watertight and q.is_winding_consistent


@pytest.mark.parametrize("identifier", ["BAG1", "BAG2", "STOPCOCK"])
def test_infusion_ward_curved_label_and_flow_arrows_have_real_material_volume(identifier):
    labels = [part for name, part in object_parts(identifier).items() if "label_" in name]
    assert len(labels) == (3 if identifier == "STOPCOCK" else 1)
    for label in labels:
        q = geometry_copy(label)
        assert q.is_watertight and q.is_winding_consistent and q.volume > 0
        assert np.all(q.area_faces > 0)


def test_infusion_ward_control_faces_are_outward_closed_volumes():
    controls = [part for name, part in object_parts("SLOT2").items() if "contec_source_control" in name]
    assert len(controls) == 9
    for control in controls:
        q = geometry_copy(control)
        assert q.is_watertight and q.is_winding_consistent and q.volume > 0
        # Controls remain completely left of the unchanged cassette channel.
        assert q.bounds[1, 0] < -0.020
