"""Asset-led picking workstation with the original task geometry and actions.

The shared Poly Haven pool is Z-up and retains embedded albedo, normal and ARM
maps. Only small functional additions (labels, a basket liner, cart pads and the
existing roller conveyor) are modelled here. All task meshes stay object-local;
the environment is authored in the original world coordinate system.
"""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from holocue.modeling import DARK, LIGHT, RUBBER, STEEL, Assembly, make_object
from holocue.models import SceneSpec
from scripts.scenes.asset_composition import mature_asset, place_asset, place_scene, textured_box


def _horizontal_levels(source: trimesh.Scene, minimum_area: float) -> list[float]:
    """Area-weighted heights of actual broad upward faces, not AABB tops."""
    mesh = source.to_mesh()
    selected = mesh.face_normals[:, 2] > 0.999
    heights = mesh.triangles_center[selected, 2]
    areas = mesh.area_faces[selected]
    _, group = np.unique(np.round(heights, 6), return_inverse=True)
    surface_area = np.bincount(group, weights=areas)
    weighted_height = np.bincount(group, weights=areas * heights)
    return sorted(
        (weighted_height[surface_area > minimum_area] / surface_area[surface_area > minimum_area]).tolist()
    )


def _crate_asset() -> trimesh.Scene:
    """Correct this scene's RGB crate material without touching the shared GLB.

    The shared crate's albedo is RGB and its factor alpha is one; its vents
    are modelled openings. BLEND disables reliable depth writing in Viser,
    while one-sided display drops inward-facing panels. Use opaque two-sided
    plastic, preserving all geometry, UVs, and the three original PBR maps.
    """
    source = mature_asset("plastic_crate_02").copy()
    for mesh in source.geometry.values():
        material = deepcopy(mesh.visual.material)
        material.alphaMode = "OPAQUE"
        material.doubleSided = True
        mesh.visual.material = material
    return source


def _task_asset(assembly: Assembly, asset_id: str, size, color, rz: float = 0) -> None:
    """Preserve UV/PBR detail while dyeing the packaging to its task color."""
    source = _crate_asset() if asset_id == "plastic_crate_02" else mature_asset(asset_id).copy()
    tint = np.asarray(color, dtype=float)
    tint = np.rint(255 * tint / tint.max()).astype(np.uint8)
    for mesh in source.geometry.values():
        material = deepcopy(mesh.visual.material)
        material.baseColorFactor = [*tint, 255]
        mesh.visual.material = material
    place_scene(assembly, source, size, (0, 0, 0), rz, asset_id)


def _level_parcel_base(assembly: Assembly, size) -> None:
    """Seat the scanned carton on real rollers without moving its task pose.

    The original scan has a low corner but a 3-10 mm lifted underside. Flatten
    its lowest 6% of height and blend over the next 6%; keep UVs, side damage,
    top shape, and the exact task envelope. This models the loaded flat base.
    """
    before = assembly.scene.bounds.copy()
    floor = -size[2] / 2
    band = size[2] * 0.06
    for node in list(assembly.scene.graph.nodes_geometry):
        transform, geometry_name = assembly.scene.graph[node]
        mesh = assembly.scene.geometry[geometry_name]
        mesh.apply_transform(transform)
        vertices = mesh.vertices.copy()
        height = vertices[:, 2] - floor
        base = height <= band
        blend = (height > band) & (height < 2 * band)
        vertices[base, 2] = floor
        vertices[blend, 2] = floor + 2 * (height[blend] - band)
        mesh.vertices = vertices
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.remove_unreferenced_vertices()
        assembly.scene.graph.update(
            frame_from=assembly.scene.graph.base_frame,
            frame_to=node,
            matrix=np.eye(4),
            geometry=geometry_name,
        )
    if not np.allclose(assembly.scene.bounds, before, atol=1e-8, rtol=0):
        raise ValueError("Levelling the parcel base changed its task envelope")
    assembly.scene.metadata["levelled_contact_base_m"] = band


def _label_mesh(assembly: Assembly, image: Image.Image, center, width: float, height: float) -> None:
    """A readable label whose front is exactly the declared local +Y plane."""
    # +X is to the viewer's left on a +Y-facing label.
    x, y, z = center
    vertices = [
        [x + width / 2, y, z - height / 2],
        [x - width / 2, y, z - height / 2],
        [x - width / 2, y, z + height / 2],
        [x + width / 2, y, z + height / 2],
    ]
    material = trimesh.visual.material.PBRMaterial(
        name="BLUE_inspection_shipping_label",
        baseColorTexture=image,
        metallicFactor=0,
        roughnessFactor=0.82,
        doubleSided=False,
    )
    visual = trimesh.visual.TextureVisuals(uv=[[0, 0], [1, 0], [1, 1], [0, 1]], material=material)
    mesh = trimesh.Trimesh(vertices=vertices, faces=[[0, 1, 2], [0, 2, 3]], visual=visual, process=False)
    key = f"{assembly.name}/{assembly.index:04d}_back_shipping_label"
    assembly.scene.add_geometry(mesh, node_name=key, geom_name=key)
    assembly.index += 1


def _front_nameplate(assembly: Assembly, size, text, width, height, background) -> None:
    """Bridge the recessed wall with a real nameplate, clear of the outer ribs."""
    front = -size[1] / 2
    depth = size[1] * 0.034
    assembly.add(
        trimesh.creation.box(extents=(width + 0.008, depth, height + 0.005)),
        DARK,
        (0, front + 0.0002 + depth / 2, 0),
        rough=0.7,
        name="front_nameplate_backing",
    )
    assembly.label(text, (0, front, 0), width, height, background=background, ink=LIGHT)


def _inspection_label(assembly: Assembly, point) -> None:
    """A rigid document pocket attached across the crate's moulded ribs."""
    x, y, z = point
    assembly.add(
        trimesh.creation.box(extents=(0.215, 0.002, 0.125)), DARK, (x, y - 0.0015, z), name="label_pocket"
    )
    for sign in (-1, 1):
        assembly.add(
            trimesh.creation.box(extents=(0.009, 0.010, 0.016)),
            DARK,
            (x + sign * 0.102, y - 0.006, z + 0.045),
            name="document_pocket_clip",
        )
    image = Image.new("RGB", (1200, 660), (241, 239, 225))
    draw = ImageDraw.Draw(image)
    regular = "DejaVuSans.ttf"
    bold = "DejaVuSans-Bold.ttf"

    def text(at, value, size=34, strong=False, fill=(30, 39, 46)):
        draw.text(at, value, font=ImageFont.truetype(bold if strong else regular, size), fill=fill)

    draw.rectangle((12, 12, 1187, 647), outline=(36, 52, 62), width=6)
    draw.rectangle((18, 18, 1181, 131), fill=(32, 83, 117))
    text((43, 31), "BLUE  /  BACK LABEL", 64, True, (245, 248, 246))
    text((45, 154), "PICKING BAY 02", 49, True)
    text((750, 162), "INSPECT", 44, True)
    draw.line((42, 229, 1156, 229), fill=(42, 53, 61), width=3)
    text((45, 250), "SKU  HC-BL-027", 43, True)
    text((730, 251), "LOT  027", 37)
    text((45, 313), "ROUTE  A-02  /  QUALITY CHECK", 37)
    text((45, 371), "RETURNABLE CRATE   |   UNIT 01", 31)
    # A binary stock-identification strip is intentionally accompanied by its
    # human-readable training ID; no machine-scanning capability is implied.
    strip = "1101001" + "".join(f"{byte:08b}" for byte in b"HC-BL-027") + "1011011"
    for i, bit in enumerate(strip):
        if bit == "1":
            draw.rectangle((48 + i * 8, 435, 53 + i * 8, 559), fill=(25, 30, 34))
    text((48, 578), "HC - BL - 027", 32)
    text((837, 438), "CHECK", 37, True)
    text((837, 490), "REAR FACE", 28)
    text((837, 545), "HOLOCUE", 26)
    _label_mesh(assembly, image, point, 0.202, 0.111)


def _cart(assembly: Assembly, name: str, center_xy, footprint, contact_z: float, pad_size) -> None:
    """Align a real cart tray plus a 3 mm service mat with the object bottom."""
    source = mature_asset("tool_cart")
    tray_z = _horizontal_levels(source, 0.1)[-1]
    pad_thickness = 0.003
    scale_z = (contact_z - pad_thickness) / (tray_z - source.bounds[0, 2])
    size = (*footprint, source.extents[2] * scale_z)
    x, y = center_xy
    place_asset(assembly, "tool_cart", size, (x, y, size[2] / 2), label=name)
    textured_box(
        assembly,
        (*pad_size, pad_thickness),
        (x, y, contact_z - pad_thickness / 2),
        "rubber_tiles",
        tile_m=0.4,
        name=name + "_service_mat",
    )
    assembly.scene.metadata[name + "_support_z_m"] = contact_z


def _roller_conveyor(assembly: Assembly) -> None:
    """Retain the original conveyor work envelope and real GREEN contact z=.86."""
    for x in (0.852, 1.308):
        textured_box(
            assembly,
            (0.022, 1.06, 0.052),
            (x, 0.70, 0.834),
            "metal_plate_02",
            tile_m=0.5,
            name="conveyor_side_rail",
        )
        for y in (0.24, 1.16):
            textured_box(
                assembly,
                (0.031, 0.031, 0.79),
                (x, y, 0.407),
                "metal_plate_02",
                tile_m=0.5,
                name="conveyor_leg",
            )
            assembly.box((0.075, 0.066, 0.012), (x, y, 0.006), RUBBER, name="conveyor_foot")
    for y in (0.24, 1.16):
        textured_box(
            assembly,
            (0.456, 0.028, 0.028),
            (1.08, y, 0.24),
            "metal_plate_02",
            tile_m=0.5,
            name="conveyor_cross_brace",
        )
    for y in np.linspace(0.20, 1.18, 23):
        assembly.cylinder(0.017, 0.438, (1.08, y, 0.843), STEEL, (1, 0, 0), "conveyor_roller")
        for x in (0.852, 1.308):
            assembly.cylinder(0.008, 0.025, (x, y, 0.843), DARK, (1, 0, 0), "roller_bearing")
    # CONV retains its original instrument mesh and exact pose. This bracket
    # connects it to the leading conveyor frame rather than leaving it afloat.
    textured_box(
        assembly,
        (0.035, 0.035, 0.145),
        (1.12, 0.19, 0.8875),
        "metal_plate_02",
        tile_m=0.4,
        name="control_bracket_post",
    )
    textured_box(
        assembly,
        (0.17, 0.265, 0.006),
        (1.12, 0.095, 0.957),
        "metal_plate_02",
        tile_m=0.4,
        name="control_bracket_plate",
    )
    assembly.label(
        "OUTBOUND  /  02", (1.321, 0.70, 0.825), 0.32, 0.040, normal=(1, 0, 0), background=(205, 181, 66)
    )


def _environment() -> Assembly:
    assembly = Assembly("shelf_picking_environment")
    # The floor and rear wall establish a modest real stockroom without
    # changing the original task camera or hiding the four working stations.
    textured_box(
        assembly,
        (4.1, 3.6, 0.055),
        (0.25, 0.35, -0.0275),
        "hangar_concrete_floor",
        tile_m=2.0,
        name="warehouse_floor",
    )
    textured_box(
        assembly,
        (4.1, 0.075, 2.65),
        (0.25, 1.65, 1.325),
        "factory_wall",
        tile_m=1.5,
        name="warehouse_back_wall",
    )
    textured_box(
        assembly,
        (4.1, 0.025, 0.12),
        (0.25, 1.598, 0.06),
        "metal_plate_02",
        tile_m=1.0,
        name="wall_kick_plate",
    )

    rack = mature_asset("worn_metal_rack")
    levels = _horizontal_levels(rack, 0.1)
    scale = 1.03 / (levels[1] - rack.bounds[0, 2])
    size = rack.extents * scale
    place_asset(assembly, "worn_metal_rack", size, (-0.34, 0.295, size[2] / 2), label="picking_rack")
    support = [(level - rack.bounds[0, 2]) * scale for level in levels]
    assembly.scene.metadata["RED_shelf_support_z_m"] = support[1]

    # Stock sits on measured source shelf surfaces; the target RED and its
    # straight departure corridor remain open on the second tier.
    stock = [
        ("wooden_crate_01", (0.36, 0.32, 0.27), (-0.58, 0.30), support[0], 0),
        ("cardboard_box_01", (0.26, 0.29, 0.24), (-0.16, 0.30), support[0], 90),
        ("cardboard_box_01", (0.23, 0.25, 0.24), (-0.66, 0.33), support[1], 90),
        ("cardboard_box_01", (0.22, 0.24, 0.17), (-0.02, 0.34), support[1], 0),
        ("cardboard_box_01", (0.37, 0.34, 0.28), (-0.57, 0.30), support[2], 90),
        ("plastic_crate_02", (0.34, 0.29, 0.23), (-0.12, 0.30), support[2], 0),
    ]
    for index, (asset_id, extents, xy, bottom, angle) in enumerate(stock):
        source = _crate_asset() if asset_id == "plastic_crate_02" else mature_asset(asset_id)
        place_scene(
            assembly,
            source,
            extents,
            (*xy, bottom + extents[2] / 2),
            rz=angle,
            label=f"shelf_stock_{index}",
        )
    assembly.label("A-02  /  PICK", (-0.34, -0.042, 0.993), 0.21, 0.036, background=(221, 193, 75))
    _cart(assembly, "basket_cart", (-0.25, -0.62), (0.64, 0.46), 0.81, (0.42, 0.34))
    _cart(assembly, "inspection_cart", (0.64, -0.14), (0.60, 0.45), 0.84, (0.34, 0.28))
    # A toolbox on the inspection cart's lower tray makes its service role
    # legible without adding clutter around the task label or rotation volume.
    cart = mature_asset("tool_cart")
    lower, upper = _horizontal_levels(cart, 0.1)
    lower_z = (lower - cart.bounds[0, 2]) * (0.84 - 0.003) / (upper - cart.bounds[0, 2])
    place_asset(
        assembly,
        "metal_toolbox",
        (0.29, 0.22, 0.13),
        (0.64, -0.14, lower_z + 0.065),
        label="inspection_cart_toolbox",
    )
    _roller_conveyor(assembly)

    # Mature background fixtures, outside every task motion corridor.
    place_asset(assembly, "hand_truck", (0.36, 0.42, 1.02), (-1.12, 1.15, 0.51), rz=12)
    assembly.label(
        "HOLOCUE  /  PICKING BAY 02\nRECEIVE  -  CHECK  -  DISPATCH",
        (0.30, 1.607, 2.13),
        0.92,
        0.19,
        background=(211, 216, 207),
        ink=(38, 65, 73),
    )
    return assembly


def build(spec: SceneSpec) -> dict[str, Assembly]:
    """Return local task meshes and a world environment without exporting files."""
    if spec.scene_id != "shelf_picking":
        raise ValueError("This builder owns only shelf_picking")
    result = {}
    for obj in spec.objects:
        assembly = Assembly(obj.object_id)
        if obj.object_id in {"RED", "GREEN"}:
            _task_asset(assembly, "cardboard_box_01", obj.size_m, obj.color, rz=90)
            if obj.object_id == "GREEN":
                _level_parcel_base(assembly, obj.size_m)
            x, y, z = obj.size_m
            assembly.label(
                obj.object_id + "\nBATCH 027",
                (0, -y / 2, 0),
                x * 0.68,
                z * 0.56,
                background=tuple(obj.color),
                ink=(243, 242, 226),
            )
            assembly.label(
                "HC / " + obj.object_id,
                (x * 0.18, 0, z / 2),
                x * 0.38,
                y * 0.42,
                normal=(0, 0, 1),
                background=(225, 218, 193),
                ink=(37, 41, 40),
            )
        elif obj.object_id in {"BLUE", "BASKET"}:
            _task_asset(assembly, "plastic_crate_02", obj.size_m, obj.color)
            if obj.object_id == "BLUE":
                _inspection_label(assembly, obj.interaction.inspect_point_local_m)
                _front_nameplate(assembly, obj.size_m, "BLUE / 027", 0.18, 0.025, (38, 80, 114))
            else:
                source = mature_asset("plastic_crate_02")
                floor = _horizontal_levels(source, 0.05)[0]
                floor_local = (
                    -obj.size_m[2] / 2 + (floor - source.bounds[0, 2]) * obj.size_m[2] / source.extents[2]
                )
                contact = obj.anchors["placement"][2]
                thickness = contact - floor_local
                if thickness <= 0:
                    raise ValueError("Basket contact must remain above the mature crate's inner floor")
                textured_box(
                    assembly,
                    (0.34, 0.26, thickness),
                    (0, 0, (floor_local + contact) / 2),
                    "rubber_tiles",
                    tile_m=0.4,
                    name="basket_inner_liner",
                )
                assembly.scene.metadata.update(
                    inner_floor_z_m=floor_local,
                    placement_support_z_m=contact,
                    liner_thickness_m=thickness,
                    liner_extent_m=[0.34, 0.26],
                )
                _front_nameplate(assembly, obj.size_m, "BASKET / A-02", 0.25, 0.03, (45, 85, 88))
        elif obj.object_id == "CONV":
            assembly = make_object(obj)
        else:
            raise ValueError(f"Unexpected shelf task object: {obj.object_id}")
        result[obj.object_id] = assembly
    result["environment"] = _environment()
    return result
