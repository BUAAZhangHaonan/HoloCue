"""Asset-led rack maintenance station, preserving the existing task geometry.

The closed server chassis comes from impresistem's CC-BY Lenovo SR250 model.
The open cabinet adapts Innerscene's CC0 layout model. Only the training slot,
fiber inspection adapter, instrument mounts and support pads are authored here.
"""

from functools import lru_cache
import xml.etree.ElementTree as ET

import cadquery as cq
import numpy as np
import trimesh

from holocue.config import root
from holocue.modeling import Assembly, DARK, RUBBER, STEEL, cad_mesh, make_object
from scripts.scenes.asset_composition import mature_asset, place_asset, place_scene, textured_box


SOURCE_DIR = "assets/downloads/server_reconstruction"
SERVER_FILE = "lenovo_sr250_impresistem.glb"


@lru_cache(maxsize=1)
def server_source():
    """Convert the original Y-up glTF to Z-up; placement fits the metre-scale envelope."""
    scene = trimesh.load_scene(root() / SOURCE_DIR / SERVER_FILE, process=False)
    scene.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return scene


@lru_cache(maxsize=1)
def rack_source():
    """Retain the source cabinet frame and perforated rails, with its door removed.

    The contract fixes the roof at 1.90 m. Shorten the plain cabinet panels, but
    trim two units off the original rails instead of shrinking their hole pitch.
    The X3D's unavailable external texture references are replaced by complete
    opaque PBR materials; its geometry and independent parts are retained.
    """
    source = ET.parse(root() / SOURCE_DIR / "innerscene_server_rack.x3d").getroot()
    result = trimesh.Scene()
    keep = set(range(14)) | set(range(20, 27)) | set(range(31, 39))
    for index, shape in enumerate(source.iter("Shape")):
        if index not in keep:
            continue
        vertices = np.fromstring(shape.find(".//Coordinate").get("point"), sep=" ").reshape(-1, 3)
        indices = np.fromstring(shape.find(".//IndexedFaceSet").get("coordIndex"), sep=" ", dtype=int)
        # The frozen source uses explicit triangles separated by -1.
        if len(indices) % 4 or not np.all(indices.reshape(-1, 4)[:, 3] == -1):
            raise ValueError("The cabinet source topology changed")
        faces = indices.reshape(-1, 4)[:, :3]
        if index in (0, 1, 2, 3, 20, 21, 22):
            vertices[:, 2] *= 1.90 / 2.017
        elif index == 5 or index in (32, 34, 36, 38):
            vertices[:, 2] -= 0.117
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        if 6 <= index <= 13:
            vertices, faces, _ = trimesh.intersections.slice_faces_plane(
                mesh.vertices, mesh.faces, (0, 0, -1), (0, 0, 1.862)
            )
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        raw = shape.find(".//Material")
        color = np.fromstring(raw.get("diffuseColor"), sep=" ")
        material = trimesh.visual.material.PBRMaterial(
            name="Innerscene_rail_steel" if 6 <= index <= 13 else "Innerscene_powder_coat",
            baseColorFactor=[*np.round(color * 255).astype(int), 255],
            metallicFactor=0.75 if 6 <= index <= 13 else 0.30,
            roughnessFactor=0.42,
        )
        mesh.visual = trimesh.visual.TextureVisuals(material=material)
        result.add_geometry(mesh, node_name=f"frame_{index:02d}", geom_name=f"frame_{index:02d}")
    return result


def fiber_adapter(assembly, obj):
    """Four open rectangular optical sockets; one remains available for inspection."""
    width, depth, height = obj.size_m
    for index, xx in enumerate(np.linspace(-width * 0.25, width * 0.25, 4)):
        socket = cq.Workplane("XY").box(0.018, 0.014, 0.010).cut(cq.Workplane("XY").box(0.013, 0.020, 0.006))
        assembly.add(cad_mesh(socket), DARK, (xx, depth / 2 + 0.006, 0.004), name="fiber_socket")
        collar = cq.Workplane("XY").box(0.020, 0.004, 0.012).cut(cq.Workplane("XY").box(0.014, 0.008, 0.007))
        assembly.add(
            cad_mesh(collar),
            (40, 175, 166) if index == 1 else STEEL,
            (xx, depth / 2 + 0.013, 0.004),
            name="fiber_live_collar" if index == 1 else "fiber_collar",
        )
        if index != 1:
            color = (46, 139, 159) if index != 3 else RUBBER
            # Keep the plug inside the collar's front plane. The cable first
            # turns outward behind the fixed inspection ring, then exits +Y.
            assembly.box((0.012, 0.006, 0.005), (xx, depth / 2 + 0.012, 0.004), color, name="fiber_plug")
            cable_x = xx + np.sign(xx) * 0.012
            tail = assembly.rod(
                (xx, depth / 2 + 0.014, 0.004),
                (cable_x, depth / 2 + 0.014, -0.006),
                0.0015,
                color,
                "fiber_cable_tail",
            )
            tail.visual.material.metallicFactor = 0.0
            tail = assembly.rod(
                (cable_x, depth / 2 + 0.014, -0.006),
                (cable_x, depth / 2 + 0.035, -0.015),
                0.0015,
                color,
                "fiber_cable_tail",
            )
            tail.visual.material.metallicFactor = 0.0
    assembly.label("OPTICAL I/O", (0, depth / 2 + 0.0004, -height * 0.32), 0.10, 0.007, (0, 1, 0))


def server_node(obj):
    result = Assembly(obj.object_id)
    # This is an explicitly documented adaptation to the frozen training envelope,
    # not an assertion that the manufacturer chassis has these exact dimensions.
    place_scene(result, server_source(), obj.size_m, (0, 0, 0), label="lenovo_sr250")
    result.label(obj.object_id, (0.13, -obj.size_m[1] / 2 - 0.0002, 0), 0.064, 0.012)
    if obj.object_id == "NODE3":
        fiber_adapter(result, obj)
    return result


def rack_slot(obj):
    result = Assembly(obj.object_id)
    width, depth, height = obj.size_m
    for xx in (-width / 2 + 0.006, width / 2 - 0.006):
        result.box((0.012, depth, height), (xx, 0, 0), STEEL, metal=0.70, name="rail_wall")
        # The bottom panel is narrower than the front mounting ears. Carry
        # that actual panel at z=1.108 m, extending each lip inward to |x|=.185.
        result.box(
            (0.047, depth, 0.005),
            (xx - np.sign(xx) * 0.0175, 0, -0.0245),
            STEEL,
            metal=0.70,
            name="rail_support",
        )
        result.label("4", (xx, -depth / 2 - 0.0002, 0), 0.011, 0.016)
    result.box((width, 0.012, height), (0, depth / 2 - 0.006, 0), DARK, name="back_stop")
    return result


@lru_cache(maxsize=1)
def cart_support_plane():
    """Measure the highest broad upward deck and its footprint in placed metres."""
    source = mature_asset("tool_cart")
    mesh = source.to_mesh()
    selected = mesh.face_normals[:, 2] > 0.999
    face_ids = np.flatnonzero(selected)
    heights = mesh.triangles_center[selected, 2]
    areas = mesh.area_faces[selected]
    _, group = np.unique(np.round(heights, 6), return_inverse=True)
    surface_area = np.bincount(group, weights=areas)
    weighted_height = np.bincount(group, weights=areas * heights)
    broad = np.flatnonzero(surface_area > 0.1)
    top = max(broad, key=lambda i: weighted_height[i] / surface_area[i])
    source_height = weighted_height[top] / surface_area[top]
    vertices = mesh.vertices[mesh.faces[face_ids[group == top]]].reshape(-1, 3)
    scale = np.array((0.55, 0.61, 0.87)) / source.extents
    placed = (vertices - source.bounds.mean(axis=0)) * scale + (0, 0, 0.435)
    footprint = np.array((placed.min(axis=0), placed.max(axis=0)))[:, :2]
    required = np.array((0.475, 0.48)) / 2
    if not (np.all(footprint[0] < -required) and np.all(footprint[1] > required)):
        raise ValueError("The service-cart riser does not fit on the source's upper deck")
    return (source_height - source.bounds[0, 2]) * scale[2]


def service_cart(assembly, cx):
    """The downloaded cart bears the pad through a riser on its measured deck."""
    place_asset(assembly, "tool_cart", (0.55, 0.61, 0.87), (cx, -0.22, 0.435), label="service_cart")
    deck = cart_support_plane()
    pad_bottom = 0.870
    assembly.box(
        (0.475, 0.48, pad_bottom - deck),
        (cx, -0.22, (pad_bottom + deck) / 2),
        DARK,
        metal=0.25,
        name="service_riser",
    )
    textured_box(assembly, (0.48, 0.49, 0.010), (cx, -0.22, 0.875), "rubber_tiles", 0.6, "service_pad")
    assembly.label("SERVICE / ESD", (cx, -0.526, 0.735), 0.30, 0.045)


def environment(spec):
    result = Assembly("server_rack_environment")
    textured_box(result, (3.2, 2.7, 0.06), (0, 0.35, -0.03), "hangar_concrete_floor", 2.0, "raised_floor")
    place_scene(result, rack_source(), (0.60, 0.70, 1.90), (0, 0.331, 0.95), label="rack_frame")
    for number, zz in enumerate(
        (0.30, 0.35, 0.40, 0.45, 0.50, 0.72, 0.77, 0.82, 0.87, 1.32, 1.37, 1.42, 1.72, 1.77)
    ):
        place_scene(
            result,
            server_source(),
            (0.432, 0.46, 0.044),
            (0, 0.26, zz),
            label=f"installed_lenovo_{number:02d}",
        )
        for xx in (-0.2065, 0.2065):
            result.add(
                trimesh.creation.box(extents=(0.043, 0.604, 0.004)),
                STEEL,
                (xx, 0.331, zz - 0.024),
                metal=0.65,
                name="installed_rail_support",
            )
    for cx in (-0.72, 0.72):
        service_cart(result, cx)
    # Short rear cable bundles stay outside the insertion corridor and inspection
    # sightline. The door is intentionally absent from the service opening.
    place_asset(
        result, "modular_electric_cables", (0.10, 0.13, 0.76), (-0.355, 0.52, 0.82), label="rear_cable_bundle"
    )
    result.box((0.18, 0.023, 0.09), (0.17, 0.0169, 1.57), DARK, metal=0.30, name="fan_control_panel")
    result.label("FAN SPEED", (0.17, 0.0051, 1.602), 0.135, 0.017)
    result.label("RACK 04", (0, -0.0202, 1.861), 0.25, 0.040)
    result.label("SLOT 4", (-0.272, -0.0202, 1.13), 0.042, 0.026)
    # The inherited beacon's lens/base assembly stops 1.6 mm above its nominal
    # envelope. This fixed mount bridges that existing offset to the cabinet roof.
    result.box((0.08, 0.08, 0.0016), (0, 0.27, 1.9008), DARK, name="alarm_mount")
    return result


def build(spec):
    result = {}
    for obj in spec.objects:
        if obj.object_id in ("SPARE", "NODE3"):
            result[obj.object_id] = server_node(obj)
        elif obj.object_id == "SLOT4":
            result[obj.object_id] = rack_slot(obj)
        else:
            result[obj.object_id] = make_object(obj)
    result["environment"] = environment(spec)
    return result
