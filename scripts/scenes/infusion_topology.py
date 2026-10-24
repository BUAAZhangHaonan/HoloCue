"""Local surface repairs for the licensed infusion teaching assets.

The source triangles, UV seams and shading normals remain the exterior. Added
faces form actual backs, film interiors and pipe walls in the exported mesh.
Nothing in this module is a collision proxy or an audit exemption.
"""

import numpy as np
import trimesh
import vtk


def topology(mesh):
    """Position-only view; do not run Trimesh's face-deleting validation."""
    points, first, inverse = np.unique(mesh.vertices, axis=0, return_index=True, return_inverse=True)
    return trimesh.Trimesh(points, inverse[mesh.faces], process=False), first, inverse


def boundary_loops(mesh):
    q, first, _ = topology(mesh)
    count = np.bincount(q.edges_unique_inverse)
    if np.any(count > 2):
        raise ValueError("repair input has a nonmanifold edge")
    mask = count[q.edges_unique_inverse] == 1
    directed = q.edges[mask]
    following = {int(a): int(b) for a, b in directed}
    if len(following) != len(directed) or len(set(following.values())) != len(directed):
        raise ValueError("repair input has a branching boundary")
    loops = []
    while following:
        start = next(iter(following))
        ring, here = [], start
        while here in following:
            ring.append(here)
            here = following.pop(here)
        if here != start:
            raise ValueError("repair input has an open boundary chain")
        loops.append(first[np.asarray(ring)])
    return loops


def _mesh_with(mesh, vertices, faces, uv, normals):
    result = trimesh.Trimesh(vertices, faces, process=False, vertex_normals=normals)
    if hasattr(mesh.visual, "material"):
        result.visual = trimesh.visual.TextureVisuals(uv=uv, material=mesh.visual.material.copy())
    else:
        result.visual = mesh.visual.copy()
    return result


def add_triangles(mesh, triangles, triangle_uv=None):
    """Append separately shaded real faces without disturbing source seams."""
    triangles = np.asarray(triangles, dtype=float).reshape(-1, 3, 3)
    if not len(triangles):
        return mesh.copy()
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    length = np.linalg.norm(cross, axis=1)
    if np.any(length <= 1e-20):
        raise ValueError("repair would add a zero-area triangle")
    vertices = np.vstack([mesh.vertices, triangles.reshape(-1, 3)])
    faces = np.vstack([mesh.faces, np.arange(len(triangles) * 3).reshape(-1, 3) + len(mesh.vertices)])
    normals = np.vstack([mesh.vertex_normals, np.repeat(cross / length[:, None], 3, axis=0)])
    original_uv = getattr(mesh.visual, "uv", None)
    uv = None
    if original_uv is not None:
        if triangle_uv is None:
            raise ValueError("textured added faces require explicit UVs")
        uv = np.vstack([original_uv, np.asarray(triangle_uv).reshape(-1, 2)])
    return _mesh_with(mesh, vertices, faces, uv, normals)


def assert_closed(mesh):
    q, _, _ = topology(mesh)
    if not q.is_watertight or not q.is_winding_consistent:
        raise ValueError("infusion surface repair did not form an oriented closed solid")
    return mesh


def inward_wall(mesh, thickness):
    """Give an open bag/pipe/sheet its finite inner wall; never cap its bore.

    A position-shared normal offset is used only for the named sheet models.
    Existing front triangles and their shading/texture values are unchanged.
    At sharp corners a least-squares plane offset retains the adjacent planes.
    """
    q, first, inverse = topology(mesh)
    if q.is_watertight:
        return mesh.copy()
    boundary = boundary_loops(mesh)
    displacement = np.zeros_like(q.vertices)
    for i, adjacent in enumerate(q.vertex_faces):
        normals = q.face_normals[adjacent[adjacent >= 0]]
        # Float32 tubes contain nearly parallel normal constraints. Their
        # unresolved axial direction must not create an enormous wall offset.
        solution = np.linalg.lstsq(normals, np.full(len(normals), -thickness), rcond=1e-4)[0]
        if np.linalg.norm(solution) > thickness * 8:
            raise ValueError("sheet corner cannot accommodate the specified inner-wall thickness")
        if np.any(normals @ solution > -0.5 * thickness):
            raise ValueError("source sheet has no consistent inward wall at a corner")
        displacement[i] = solution
    inside = mesh.vertices + displacement[inverse]
    triangles = [inside[mesh.faces[:, ::-1]]]
    original_uv = getattr(mesh.visual, "uv", None)
    uvs = [original_uv[mesh.faces[:, ::-1]]] if original_uv is not None else None
    for ring in boundary:
        for a, b in zip(ring, np.roll(ring, -1)):
            triangles.append(
                np.asarray(
                    [
                        [mesh.vertices[b], mesh.vertices[a], inside[a]],
                        [mesh.vertices[b], inside[a], inside[b]],
                    ]
                )
            )
            if uvs is not None:
                uvs.append(
                    np.asarray(
                        [
                            [original_uv[b], original_uv[a], original_uv[a]],
                            [original_uv[b], original_uv[a], original_uv[b]],
                        ]
                    )
                )
    result = add_triangles(mesh, np.concatenate(triangles), None if uvs is None else np.concatenate(uvs))
    return assert_closed(result)


def translated_sheet(mesh, vector):
    """Extrude a known front sheet into its backing, retaining the front face."""
    inside = mesh.vertices + np.asarray(vector)
    triangles = [inside[mesh.faces[:, ::-1]]]
    uv = getattr(mesh.visual, "uv", None)
    added_uv = [uv[mesh.faces[:, ::-1]]] if uv is not None else None
    for ring in boundary_loops(mesh):
        for a, b in zip(ring, np.roll(ring, -1)):
            triangles.append(
                np.asarray(
                    [
                        [mesh.vertices[b], mesh.vertices[a], inside[a]],
                        [mesh.vertices[b], inside[a], inside[b]],
                    ]
                )
            )
            if added_uv is not None:
                added_uv.append(np.asarray([[uv[b], uv[a], uv[a]], [uv[b], uv[a], uv[b]]]))
    return assert_closed(
        add_triangles(mesh, np.concatenate(triangles), None if added_uv is None else np.concatenate(added_uv))
    )


def stitch_collinear_faces(mesh):
    """Replace the case's zero-area T-junction triangles by real edge splits."""
    q, _, inverse = topology(mesh)
    cross = np.cross(q.triangles[:, 1] - q.triangles[:, 0], q.triangles[:, 2] - q.triangles[:, 0])
    degenerate = np.flatnonzero(np.linalg.norm(cross, axis=1) < 1e-20)
    remove = set(degenerate.tolist())
    triangles, texture = [], []
    uv = getattr(mesh.visual, "uv", None)
    for fi in degenerate:
        face = q.faces[fi]
        pairs = [(face[0], face[1], face[2]), (face[1], face[2], face[0]), (face[2], face[0], face[1])]
        a, b, mid = max(pairs, key=lambda ids: np.linalg.norm(q.vertices[ids[0]] - q.vertices[ids[1]]))
        neighbors = np.flatnonzero(np.any(q.faces == a, axis=1) & np.any(q.faces == b, axis=1))
        neighbors = [int(n) for n in neighbors if n not in degenerate]
        if len(neighbors) != 1:
            raise ValueError("collinear source face is not an isolated T junction")
        other = neighbors[0]
        if other in remove:
            raise ValueError("two degenerate faces share an unsupported split target")
        remove.add(other)
        raw = mesh.faces[other]
        ids = inverse[raw]
        edge = next(i for i in range(3) if {int(ids[i]), int(ids[(i + 1) % 3])} == {int(a), int(b)})
        u, v, w = np.roll(raw, -edge)
        point = q.vertices[mid]
        triangles.extend(
            [[mesh.vertices[u], point, mesh.vertices[w]], [point, mesh.vertices[v], mesh.vertices[w]]]
        )
        if uv is not None:
            delta = mesh.vertices[v] - mesh.vertices[u]
            t = np.dot(point - mesh.vertices[u], delta) / np.dot(delta, delta)
            middle_uv = (1 - t) * uv[u] + t * uv[v]
            texture.extend([[uv[u], middle_uv, uv[w]], [middle_uv, uv[v], uv[w]]])
    result = mesh.copy()
    result.update_faces(np.asarray([i not in remove for i in range(len(mesh.faces))]))
    result = add_triangles(result, triangles, texture if uv is not None else None)
    return assert_closed(result)


def cap_contours(mesh, rings):
    """Triangulate a documented missing back face, retaining holes in it."""
    points = np.concatenate([mesh.vertices[ring] for ring in rings])
    center = points.mean(axis=0)
    _, _, basis = np.linalg.svd(points - center, full_matrices=False)
    projected = (points - center) @ basis[:2].T
    vtk_points = vtk.vtkPoints()
    vtk_points.SetDataTypeToDouble()
    for x, y in projected:
        vtk_points.InsertNextPoint(float(x), float(y), 0.0)
    lines = vtk.vtkCellArray()
    offset = 0
    for ring in rings:
        for i in range(len(ring)):
            lines.InsertNextCell(2)
            lines.InsertCellPoint(offset + i)
            lines.InsertCellPoint(offset + (i + 1) % len(ring))
        offset += len(ring)
    data = vtk.vtkPolyData()
    data.SetPoints(vtk_points)
    data.SetLines(lines)
    triangulator = vtk.vtkContourTriangulator()
    triangulator.SetInputData(data)
    triangulator.Update()
    output = triangulator.GetOutput()
    ids = np.asarray(
        [[output.GetCell(i).GetPointId(j) for j in range(3)] for i in range(output.GetNumberOfCells())],
        dtype=int,
    )
    if not len(ids):
        raise ValueError("missing back face could not be triangulated")
    raw_ids = np.concatenate(rings)
    # Orient from an existing boundary edge; its new incident face must oppose it.
    for ring in rings:
        for a, b in zip(ring, np.roll(ring, -1)):
            ca = np.flatnonzero(raw_ids == a)[0]
            cb = np.flatnonzero(raw_ids == b)[0]
            where = np.flatnonzero(np.any(ids == ca, axis=1) & np.any(ids == cb, axis=1))
            if len(where):
                tri = ids[where[0]]
                ai = np.flatnonzero(tri == ca)[0]
                if tri[(ai + 1) % 3] == cb:
                    ids = ids[:, ::-1]
                break
        else:
            continue
        break
    uv = getattr(mesh.visual, "uv", None)
    return add_triangles(mesh, points[ids], None if uv is None else uv[raw_ids[ids]])


def small_holes(mesh):
    """Restore the monitor's documented three/four-edge missing triangles."""
    result = mesh.copy()
    for ring in boundary_loops(mesh):
        if len(ring) not in (3, 4):
            raise ValueError("monitor repair encountered an undocumented opening")
        result = cap_contours(result, [ring])
    return assert_closed(result)


def caps(mesh, expected_sizes):
    """Close named nonfunctional component backs, not arbitrary source holes."""
    rings = boundary_loops(mesh)
    if sorted(map(len, rings)) != sorted(expected_sizes):
        raise ValueError("source component opening pattern changed")
    result = mesh.copy()
    for ring in rings:
        result = cap_contours(result, [ring])
    return assert_closed(result)


def bridge_matching_rings(mesh, first, second, axis):
    """Complete a source through-bore wall between its two existing rims."""
    a, b = mesh.vertices[first], mesh.vertices[second]
    axes = [i for i in range(3) if i != axis]
    distance = np.linalg.norm(a[:, None, axes] - b[None, :, axes], axis=2)
    order = np.argmin(distance, axis=1)
    if (
        len(first) != len(second)
        or len(set(order)) != len(order)
        or distance[np.arange(len(order)), order].max() > 1e-12
    ):
        raise ValueError("source bore rims do not match")
    second = second[order]
    triangles, texture = [], []
    uv = getattr(mesh.visual, "uv", None)
    for i in range(len(first)):
        j = (i + 1) % len(first)
        ids = [[first[j], first[i], second[i]], [first[j], second[i], second[j]]]
        triangles.extend(mesh.vertices[ids])
        if uv is not None:
            texture.extend(uv[ids])
    return add_triangles(mesh, triangles, texture if uv is not None else None)


def interface_from_source(mesh, ring, donor):
    """Restore a missing material interface using its neighbor's real faces."""
    points = mesh.vertices[ring]
    q, _, _ = topology(donor)
    lookup = {tuple(point): i for i, point in enumerate(q.vertices)}
    try:
        ids = [lookup[tuple(point)] for point in points]
    except KeyError as error:
        raise ValueError("control interface positions no longer match") from error
    edges = {tuple(sorted((a, b))) for a, b in zip(ids, np.roll(ids, -1))}
    adjacency = [
        pair
        for pair, edge in zip(q.face_adjacency, q.face_adjacency_edges)
        if tuple(sorted(edge)) not in edges
    ]
    groups = trimesh.graph.connected_components(
        np.asarray(adjacency), nodes=np.arange(len(q.faces)), min_len=1
    )
    patch = None
    for group in groups:
        candidate = q.faces[group]
        all_edges = np.sort(candidate[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
        unique, counts = np.unique(all_edges, axis=0, return_counts=True)
        boundary = {tuple(edge) for edge in unique[counts == 1]}
        if boundary == edges:
            if patch is not None:
                raise ValueError("source control interface has two candidate patches")
            patch = group
    if patch is None:
        raise ValueError("source donor has no matching control interface")
    faces = q.faces[patch].copy()
    a, b = ids[:2]
    face = next(face for face in faces if a in face and b in face)
    ai = int(np.flatnonzero(face == a)[0])
    flip = face[(ai + 1) % 3] == b
    source_faces = donor.faces[patch]
    if flip:
        source_faces = source_faces[:, ::-1]
    uv = getattr(mesh.visual, "uv", None)
    donor_uv = getattr(donor.visual, "uv", None)
    if uv is not None and donor_uv is None:
        raise ValueError("textured interface has no source UVs")
    return add_triangles(mesh, donor.vertices[source_faces], None if uv is None else donor_uv[source_faces])


def trim_cart_base_slivers(mesh):
    """Trim four tiny opposed-face source burrs; preserve its four closed bodies.

    These are real zero-thickness protrusions, not coincident body faces. Their
    deletion is intentionally confined to this named source component.
    """
    q, _, _ = topology(mesh)
    groups = trimesh.graph.connected_components(q.face_adjacency, nodes=np.arange(len(q.faces)), min_len=1)
    keep, burrs, bodies = [], 0, 0
    for ids in groups:
        part = q.submesh([ids], append=True, repair=False)
        if len(ids) == 260 and part.is_watertight and part.is_winding_consistent:
            keep.extend(ids)
            bodies += 1
            continue
        if len(ids) != 2 or not np.array_equal(np.sort(q.faces[ids[0]]), np.sort(q.faces[ids[1]])):
            raise ValueError("cart base has an unrecognized source component")
        if q.face_normals[ids[0]] @ q.face_normals[ids[1]] > -0.999999:
            raise ValueError("cart base source sliver is not an opposing face pair")
        # The adaptation uses metres; no broad small-component deletion rule.
        if part.extents.max() > 0.0006:
            raise ValueError("cart base burr exceeds the documented source size")
        burrs += 1
    if bodies != 4 or burrs != 4:
        raise ValueError("cart base source structure changed")
    result = mesh.copy()
    result.update_faces(np.sort(keep))
    return assert_closed(result)


def backing_plane(mesh, axis, coordinate):
    """Complete the frame's zero-thickness rear regions with a real back."""
    rings = boundary_loops(mesh)
    triangles, texture = [], []
    uv = getattr(mesh.visual, "uv", None)
    for ring in rings:
        front = mesh.vertices[ring]
        back = front.copy()
        back[:, axis] = coordinate
        for i in range(len(ring)):
            j = (i + 1) % len(ring)
            triangles.extend([[front[j], front[i], back[i]], [front[j], back[i], back[j]]])
            if uv is not None:
                texture.extend(
                    [[uv[ring[j]], uv[ring[i]], uv[ring[i]]], [uv[ring[j]], uv[ring[i]], uv[ring[j]]]]
                )
    result = add_triangles(mesh, triangles, texture if uv is not None else None)
    result = cap_contours(result, boundary_loops(result))
    return assert_closed(result)


def outward(mesh):
    """Orient the source's inward-facing control surfaces after closure."""
    result = assert_closed(mesh.copy())
    q, _, _ = topology(result)
    before = q.faces.copy()
    trimesh.repair.fix_normals(q, multibody=True)
    flip = np.any(q.faces != before, axis=1)
    # Connectivity is positional, whereas the render mesh retains UV/normal
    # splits. Apply the component orientation back to the original faces.
    faces = result.faces.copy()
    faces[flip] = faces[flip, ::-1]
    result.faces = faces
    return assert_closed(result)


def wheel_tread(mesh):
    """Loft the missing curved lower tread between its genuine side profiles.

    The source has two complete lower tire-side arcs and two eight-point
    axial borders. Their ruled loft restores tread curvature and preserves
    every source point, including floor contact. A planar cap would cut
    through the tire. The separate eight-edge mounting back is planar.
    """
    rings = boundary_loops(mesh)
    if sorted(map(len, rings)) != [8, 34]:
        raise ValueError("IV-stand wheel opening pattern changed")
    ring = next(r for r in rings if len(r) == 34)
    p = mesh.vertices[ring]
    horizontal = np.abs(np.roll(p, -1, axis=0)[:, 2] - p[:, 2]) < 1e-7
    starts = np.flatnonzero(horizontal & ~np.roll(horizontal, 1))
    if len(starts) != 2:
        raise ValueError("wheel tread no longer has its two axial borders")
    start = int(starts[0])
    ring = np.roll(ring, -start)
    p = mesh.vertices[ring]
    horizontal = np.roll(horizontal, -start)
    width_edges = next(i for i in range(len(ring)) if not horizontal[i])
    other = int(np.flatnonzero(horizontal & ~np.roll(horizontal, 1))[1])
    if width_edges != 7 or other != 17:
        raise ValueError("wheel tread source sampling changed")
    right_ids = ring[7:18]
    left_ids = np.r_[ring[24:], ring[:1]][::-1]
    left, right = mesh.vertices[left_ids], mesh.vertices[right_ids]
    if len(left) != 11 or len(right) != 11:
        raise ValueError("wheel tread source side arcs changed")
    u = np.linalg.norm(p[:8] - p[0], axis=1) / np.linalg.norm(p[7] - p[0])
    grid = left[:, None] * (1 - u[None, :, None]) + right[:, None] * u[None, :, None]
    grid[0] = p[:8]
    grid[-1] = p[17:25][::-1]
    # Use exact original arc coordinates rather than their arithmetic copies.
    grid[:, 0], grid[:, -1] = left, right
    uv = getattr(mesh.visual, "uv", None)
    texture_grid = None
    if uv is not None:
        texture_grid = uv[left_ids, None] * (1 - u[None, :, None]) + uv[right_ids, None] * u[None, :, None]
    triangles, texture = [], []
    for row in range(10):
        for col in range(7):
            ids = [
                [(row, col + 1), (row, col), (row + 1, col)],
                [(row, col + 1), (row + 1, col), (row + 1, col + 1)],
            ]
            triangles.extend([[grid[r, c] for r, c in face] for face in ids])
            if uv is not None:
                texture.extend([[texture_grid[r, c] for r, c in face] for face in ids])
    result = add_triangles(mesh, triangles, texture if uv is not None else None)
    remaining = boundary_loops(result)
    if len(remaining) != 1 or len(remaining[0]) != 8:
        raise ValueError("wheel tread loft did not join its complete source boundary")
    return assert_closed(cap_contours(result, remaining))
