"""Finish incomplete CNC source surfaces as actual textured physical solids.

Repairs are made before glTF export.  The audit does not call this module.
Original visible triangles and their UV corners are retained; missing rear
faces and the inner faces of specified sheet parts are added to the model.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import trimesh
import vtk


def copy_mesh(mesh, face_indices=None):
    """Copy geometry/UV data while sharing the immutable licensed textures."""
    source_faces = mesh.faces if face_indices is None else mesh.faces[face_indices]
    if face_indices is None:
        selected = np.arange(len(mesh.vertices))
        faces = source_faces.copy()
    else:
        selected, inverse = np.unique(source_faces.reshape(-1), return_inverse=True)
        faces = inverse.reshape(-1, 3)
    visual = mesh.visual
    if visual.kind == "texture":
        uv = None if visual.uv is None else visual.uv[selected]
        visual = trimesh.visual.TextureVisuals(uv=uv, material=visual.material)
    elif visual.kind == "vertex":
        visual = trimesh.visual.ColorVisuals(vertex_colors=visual.vertex_colors[selected])
    else:
        visual = visual.copy()
    return trimesh.Trimesh(
        vertices=mesh.vertices[selected],
        faces=faces,
        visual=visual,
        process=False,
        metadata=mesh.metadata.copy(),
    )


def _combine(meshes):
    vertices, faces, uv = [], [], []
    count = 0
    for mesh in meshes:
        vertices.append(mesh.vertices)
        faces.append(mesh.faces + count)
        uv.append(mesh.visual.uv)
        count += len(mesh.vertices)
    visual = trimesh.visual.TextureVisuals(uv=np.vstack(uv), material=meshes[0].visual.material)
    return trimesh.Trimesh(np.vstack(vertices), np.vstack(faces), visual=visual, process=False)


def _pack_solids(meshes):
    """Pack same-material closed solids without joining coincident contact edges.

    Each physical part stays a separate connected solid. A small graph coloring
    keeps touching parts with identical edges in different glTF primitives; other
    parts share one primitive and one texture allocation in downstream consumers.
    """
    all_vertices = np.vstack([m.vertices for m in meshes])
    _, inverse = np.unique(all_vertices, axis=0, return_inverse=True)
    owners = {}
    graph = nx.Graph()
    graph.add_nodes_from(range(len(meshes)))
    start = 0
    for index, mesh in enumerate(meshes):
        remap = inverse[start : start + len(mesh.vertices)]
        edges = np.unique(np.sort(remap[mesh.edges], axis=1), axis=0)
        for edge in map(tuple, edges):
            for previous in owners.get(edge, []):
                graph.add_edge(index, previous)
            owners.setdefault(edge, []).append(index)
        start += len(mesh.vertices)
    colors = nx.coloring.greedy_color(graph, strategy="largest_first")
    groups = []
    for color in range(max(colors.values()) + 1):
        members = [m for i, m in enumerate(meshes) if colors[i] == color]
        packed = _combine(members)
        packed.metadata["cnc_physical_parts"] = [m.metadata for m in members]
        groups.append(_check(packed, "packed CNC closed solids"))
    return groups


def topology(mesh):
    """Index coincident positions without altering the rendered UV seams."""
    vertices, first, inverse = np.unique(mesh.vertices, axis=0, return_index=True, return_inverse=True)
    return trimesh.Trimesh(vertices, inverse[mesh.faces], process=False), first, inverse


def _check(mesh, label):
    check, _, _ = topology(mesh)
    if not check.is_watertight or not check.is_winding_consistent:
        edges, count = np.unique(check.edges_sorted, axis=0, return_counts=True)
        raise ValueError(
            f"{label}: not a closed solid: {sum(count == 1)} boundary, {sum(count > 2)} overfull"
        )
    if check.volume <= 0:
        raise ValueError(f"{label}: nonpositive volume {check.volume}")
    return mesh


def _orient(mesh):
    check, _, _ = topology(mesh)
    check.fix_normals(multibody=True)
    # The geometry arrays have identical face order; only winding may change.
    flipped = np.any(check.faces != topology(mesh)[0].faces, axis=1)
    result = copy_mesh(mesh)
    result.faces[flipped] = result.faces[flipped, ::-1]
    result._cache.clear()
    return result


def boundary_cycles(mesh):
    """Oriented boundary cycles, including several holes touching at one point."""
    check, _, _ = topology(mesh)
    edges, inverse, count = np.unique(check.edges_sorted, axis=0, return_inverse=True, return_counts=True)
    boundary = check.edges[count[inverse] == 1]
    if not len(boundary):
        return []
    graph = nx.DiGraph()
    graph.add_edges_from(boundary.tolist())
    cycles = [np.asarray(c, dtype=np.int64) for c in nx.simple_cycles(graph)]
    covered = sum(len(c) for c in cycles)
    if covered != len(boundary):
        raise ValueError(f"Boundary does not decompose into disjoint cycles: {covered}/{len(boundary)}")
    return cycles


def _triangulate(vertices, cycles, normal=None):
    """Use VTK's constrained contour triangulator; keep all boundary vertices."""
    if normal is None:
        p = vertices[cycles[0]]
        normal = np.cross(p, np.roll(p, -1, axis=0)).sum(axis=0)
        normal /= np.linalg.norm(normal)
    origin = vertices[cycles[0]].mean(0)
    projected = vertices - np.outer((vertices - origin) @ normal, normal)
    points = vtk.vtkPoints()
    points.SetDataTypeToDouble()
    for v in projected:
        points.InsertNextPoint(*v)
    lines = vtk.vtkCellArray()
    for cycle in cycles:
        for a, b in zip(cycle, np.roll(cycle, -1)):
            lines.InsertNextCell(2)
            lines.InsertCellPoint(int(a))
            lines.InsertCellPoint(int(b))
    data = vtk.vtkPolyData()
    data.SetPoints(points)
    data.SetLines(lines)
    triangles = vtk.vtkCellArray()
    ok = vtk.vtkContourTriangulator.TriangulateContours(data, 0, lines.GetNumberOfCells(), triangles, normal)
    if not ok:
        raise ValueError("Source boundary could not be triangulated without moving its contour")
    ids = vtk.vtkIdList()
    triangles.InitTraversal()
    faces = []
    while triangles.GetNextCell(ids):
        if ids.GetNumberOfIds() != 3:
            raise ValueError("Nontriangular cap")
        faces.append([ids.GetId(i) for i in range(3)])
    return np.asarray(faces, dtype=np.int64)


def _with_extra_faces(mesh, faces):
    """Map cap corners to existing source corners without rewriting source UVs."""
    _, first, _ = topology(mesh)
    result = copy_mesh(mesh)
    result.faces = np.vstack([result.faces, first[np.asarray(faces)]])
    result._cache.clear()
    return result


def _small_spatial_patch(vertices, cycle, existing_edges):
    """Minimum-area triangulation of a small, genuinely nonplanar sheet seam."""
    from functools import lru_cache

    boundary = {tuple(sorted((int(a), int(b)))) for a, b in zip(cycle, np.roll(cycle, -1))}

    @lru_cache(None)
    def solve(begin, end):
        if end <= begin + 1:
            return 0.0, []
        best = (float("inf"), [])
        for middle in range(begin + 1, end):
            tri = [int(cycle[i]) for i in (begin, middle, end)]
            sides = [tuple(sorted((a, b))) for a, b in zip(tri, np.roll(tri, -1))]
            if any(e in existing_edges and e not in boundary for e in sides):
                continue
            p = vertices[tri]
            area = np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])) / 2
            if area <= 1e-16:
                continue
            left, lf = solve(begin, middle)
            right, rf = solve(middle, end)
            candidate = (left + right + area, [*lf, *rf, tri])
            if candidate[0] < best[0]:
                best = candidate
        return best

    cost, result = solve(0, len(cycle) - 1)
    if not np.isfinite(cost):
        raise ValueError("No valid local seam triangulation")
    return np.asarray(result)


def cap_hidden_faces(mesh, label, spatial_seams=False):
    """Close omitted rear/end faces of volumetric hardware, using its contour."""
    result = _orient(mesh)
    check, _, _ = topology(result)
    if check.is_watertight:
        return _check(result, label)
    cycles = boundary_cycles(result)
    existing_edges = set(map(tuple, check.edges_unique))
    faces = []
    for cycle in cycles:
        # These contours are specific hidden end cuts. The original vertices
        # retain their slight scan/nonplanar deviations during triangulation.
        try:
            cap = (
                _small_spatial_patch(check.vertices, cycle, existing_edges)
                if spatial_seams and len(cycle) <= 5
                else _triangulate(check.vertices, [cycle])
            )
        except ValueError as exc:
            raise ValueError(f"{label}: {len(cycle)} vertex hidden face: {exc}") from exc
        faces.extend(cap)
    result = _orient(_with_extra_faces(result, faces))
    return _check(result, label)


def finite_wall(mesh, thickness, label, smooth=False):
    """Add an inward wall and rim to an actual open sheet/tube source part.

    The source skin stays in its exact original position. At folds, a least-squares
    intersection of incident face offset planes gives a miter rather than shrinking
    the component towards an arbitrary center. Every boundary is rimmed, so holes
    remain open and are not replaced by disks across their mouths.
    """
    mesh = _orient(mesh)
    check, _, inverse = topology(mesh)
    _, count = np.unique(check.edges_sorted, axis=0, return_counts=True)
    if np.any(count > 2):
        raise ValueError(f"{label}: finite wall requires a manifold source sheet")
    normals = [[] for _ in check.vertices]
    for face, normal in zip(check.faces, check.face_normals):
        for vertex in face:
            normals[vertex].append(normal)
    displacement = np.zeros_like(check.vertices)
    for i, values in enumerate(normals):
        ns = np.unique(np.round(values, 7), axis=0)
        displacement[i] = np.linalg.lstsq(ns, np.full(len(ns), -thickness), rcond=1e-4)[0]
    if smooth:
        # A curved flexible tape has smooth offset normals, not intersections
        # of nearly opposing planes across its fine surface wrinkles.
        displacement = -thickness * check.vertex_normals
    maximum = np.linalg.norm(displacement, axis=1).max()
    if maximum > thickness * 5:
        raise ValueError(f"{label}: source fold miter {maximum} exceeds five wall thicknesses")
    vertices = np.vstack([mesh.vertices, mesh.vertices + displacement[inverse]])
    n = len(mesh.vertices)
    faces = [mesh.faces, mesh.faces[:, ::-1] + n]
    topo_edges, inv, counts = np.unique(check.edges_sorted, axis=0, return_inverse=True, return_counts=True)
    raw_boundary = mesh.edges[counts[inv] == 1]
    walls = []
    for a, b in raw_boundary:
        walls.extend([[b, a, a + n], [b, a + n, b + n]])
    faces.append(np.asarray(walls))
    visual = mesh.visual
    if visual.kind == "texture":
        visual = trimesh.visual.TextureVisuals(uv=np.vstack([visual.uv, visual.uv]), material=visual.material)
    elif visual.kind == "vertex":
        visual = trimesh.visual.ColorVisuals(
            vertex_colors=np.vstack([visual.vertex_colors, visual.vertex_colors])
        )
    result = trimesh.Trimesh(vertices, np.vstack(faces), visual=visual, process=False)
    result = _orient(result)
    return _check(result, label)


def source_components(mesh):
    """Separate physical surface components where the source joins several solids.

    No faces are discarded. Edges with more than two incident faces do not define
    manifold adjacency, matching the source's touching hardware and separate sheets.
    """
    check, _, _ = topology(mesh)
    groups = trimesh.graph.connected_components(
        check.face_adjacency, nodes=np.arange(len(check.faces)), min_len=1
    )
    return [copy_mesh(mesh, group) for group in groups]


def repair_mature_scene(source, asset_id):
    """Apply explicit part prescriptions to the licensed CNC background assets."""
    result = trimesh.Scene()
    for node in source.graph.nodes_geometry:
        transform, key = source.graph[node]
        parts = source_components(source.geometry[key])
        paired_caps = {67: 69, 71: 72, 74: 75, 77: 78} if asset_id == "tool_cart" else {}
        solids = []
        for index, mesh in enumerate(parts):
            if index in paired_caps.values():
                continue  # this exact source disk is retained with its cap
            if index in paired_caps:
                mesh = _combine([mesh, parts[paired_caps[index]]])
            label = f"{asset_id}/{node}/part_{index:03d}"
            check, _, _ = topology(mesh)
            thickness = None
            if asset_id == "tool_cart":
                if index in (135, 136, 137, 138, 149, 150, 151):
                    thickness = 0.0012  # folded steel shelf, drawer skins and slides
                elif index in (68, 70, 73, 76):
                    thickness = 0.0008  # open caster sleeves; retain both openings
            elif asset_id == "WoodenTable_03":
                if key == "Cube.005" and index == 0:
                    thickness = 0.006  # the source's single-plane wooden backing
                elif (key == "Cube.005" and index in (3, 10)) or (key == "Cube.002" and index in (39, 42)):
                    thickness = 0.0008  # bent drawer hardware
                elif key == "Cube.002" and index == 45:
                    thickness = 0.004  # bottom board with omitted inner skin
            elif asset_id == "metal_toolbox":
                if key == "Cube.012" and index in (*range(12), 14, 15, 39):
                    thickness = 0.00045
                elif key == "Cylinder.015" and index in (29, *range(32, 40)):
                    thickness = 0.00045
                elif key == "Cylinder.021" and index == 4:
                    thickness = 0.00045
            elif asset_id == "lubricant_spray" and key == "Plane.006":
                thickness = 0.00015  # actual curved tape/label sheet
            if check.is_watertight:
                repaired = _check(_orient(mesh), label)
            elif thickness is not None:
                smooth = asset_id == "lubricant_spray" or (
                    asset_id == "tool_cart" and index in (135, 136, 149)
                )
                repaired = finite_wall(mesh, thickness, label, smooth=smooth)
            else:
                repaired = cap_hidden_faces(
                    mesh, label, spatial_seams=asset_id == "tool_cart" and index == 134
                )
            repaired.metadata["cnc_source_part"] = label
            repaired.metadata["cnc_repair"] = (
                "inward_finite_wall" if thickness else "existing_solid_or_hidden_end_faces"
            )
            if thickness:
                repaired.metadata["wall_thickness_m"] = thickness
            solids.append(repaired)
        for index, packed in enumerate(_pack_solids(solids)):
            name = f"{node}_solids_{index:02d}"
            result.add_geometry(packed, node_name=name, geom_name=name, transform=transform)
    return result


def replace_planar_faces(mesh, axis, value, label, tolerance=1e-9):
    """Retessellate a defective CAD plane against the unchanged side contours."""
    result = copy_mesh(mesh)
    on_plane = np.abs(result.triangles[:, :, axis] - value) <= tolerance
    result.update_faces(~on_plane.all(axis=1))
    check, _, _ = topology(result)
    cycles = boundary_cycles(result)
    selected = [c for c in cycles if np.max(np.abs(check.vertices[c, axis] - value)) <= tolerance]
    if not selected:
        raise ValueError(f"{label}: no complete source contour on requested plane")
    # VTK distinguishes interior contours by winding relative to the outer
    # contour. Bottom and top source contours have opposite orientations.
    areas = [np.cross(check.vertices[c], np.roll(check.vertices[c], -1, axis=0)).sum(0) for c in selected]
    normal = max(areas, key=np.linalg.norm)
    normal /= np.linalg.norm(normal)
    faces = _triangulate(check.vertices, selected, normal)
    result = _with_extra_faces(result, faces)
    return _orient(result)


def repair_post(mesh):
    """Keep the original T-slot side walls; reconstruct the two CAD end faces."""
    result = copy_mesh(mesh)
    check, _, _ = topology(result)
    # The CAD export repeats sixteen exact end triangles.
    _, first = np.unique(np.sort(check.faces, axis=1), axis=0, return_index=True)
    result.update_faces(np.sort(first))
    for z in (0.0, 1.5):
        result = replace_planar_faces(result, 2, z, "Araki 3030 end profile")
    return _check(_orient(result), "Araki 3030 extrusion")


def repair_flange(mesh):
    """Complete the cropped flange's bore and CAD planes from source contours."""
    result = topology(mesh)[0]
    bottom = float(result.bounds[0, 2])
    radius = np.linalg.norm(result.vertices[:, :2], axis=1)
    lower = np.flatnonzero((np.abs(result.vertices[:, 2] - bottom) < 1e-9) & (np.abs(radius - 0.015) < 1e-7))
    upper = np.flatnonzero((np.abs(result.vertices[:, 2]) < 1e-9) & (np.abs(radius - 0.015875) < 1e-7))
    if len(lower) != 64 or len(upper) != 64:
        raise ValueError("The source flange's two bore contours changed")
    lower = lower[np.argsort(np.arctan2(result.vertices[lower, 1], result.vertices[lower, 0]))]
    upper = upper[np.argsort(np.arctan2(result.vertices[upper, 1], result.vertices[upper, 0]))]
    faces = []
    for i in range(64):
        j = (i + 1) % 64
        faces.extend([[lower[i], lower[j], upper[j]], [lower[i], upper[j], upper[i]]])
    result.faces = np.vstack([result.faces, faces])
    # The old underside has a 64-segment outer ring but the retained side wall
    # has a different tessellation. Rebuild that plane against the actual wall.
    result = replace_planar_faces(result, 2, bottom, "flange underside")
    for y in (-0.016299987211823463, 0.016299987211823463):
        result = replace_planar_faces(result, 1, y, "flange drive-notch wall")
    result = replace_planar_faces(result, 2, 0.0, "flange upper plane")
    return _check(_orient(result), "Araki cropped flange")


def repair_er(source):
    """Orient ER solids; remove the two identified isolated export fragments."""
    result = source.copy()
    for key, mesh in list(result.geometry.items()):
        pieces = source_components(mesh)
        if len(pieces) == 1:
            result.geometry[key] = _check(_orient(mesh), key)
            continue
        closed = [p for p in pieces if topology(p)[0].is_watertight]
        if len(closed) != 1:
            raise ValueError(f"Unexpected ER topology {key}")
        main = closed[0]
        expected = [
            np.asarray(
                [
                    [0.4453280568122864, -0.2244793176651001, 0.08982637524604797],
                    [0.4462914764881134, -0.22816383838653564, 0.09301174432039261],
                    [0.4483736455440521, -0.2238251268863678, 0.0936138927936554],
                ]
            ),
            np.asarray(
                [
                    [0.3850739896297455, -0.22095786035060883, 0.021531475707888603],
                    [0.38836634159088135, -0.22365033626556396, 0.022143542766571045],
                    [0.37889695167541504, -0.22109270095825195, 0.01718848943710327],
                ]
            ),
        ]
        if key != "vl002b_defaultMat.003_0.007" or len(mesh.faces) != 13998 or len(main.faces) != 13996:
            raise ValueError("Unexpected cutter source; do not generalize fragment removal")
        fragments = [p for p in pieces if p is not main]
        if len(fragments) != 2:
            raise ValueError("Expected exactly two diagnosed isolated cutter triangles")
        removed = []
        for fragment in fragments:
            if fragment is main:
                continue
            if len(fragment.faces) != 1:
                raise ValueError(f"Unexpected cutter fragment in {key}")
            vertices = fragment.vertices
            if not any(np.array_equal(np.sort(vertices, axis=0), np.sort(v, axis=0)) for v in expected):
                raise ValueError("Unrecognized isolated cutter triangle")
            samples = np.vstack([fragment.vertices, fragment.triangles.mean(axis=1)])
            _, distance, _ = trimesh.proximity.closest_point_naive(topology(main)[0], samples)
            removed.append(
                {
                    "vertices_source_units": vertices.tolist(),
                    "sample_distance_source_units": distance.tolist(),
                }
            )
        main.metadata["removed_isolated_export_triangles"] = removed
        main.metadata["complete_closed_cutter_faces"] = 13996
        result.geometry[key] = _check(_orient(main), key)
    return result
