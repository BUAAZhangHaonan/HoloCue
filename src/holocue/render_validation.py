"""Independent CPU rendering of the actual glTF meshes through VTK OSMesa."""

from __future__ import annotations

import numpy as np
import trimesh
import vtk
from PIL import Image
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy, numpy_to_vtkIdTypeArray


def studio_texture():
    y, x = np.mgrid[0:64, 0:128]
    ambient = 0.16 + 0.17 * np.maximum(np.sin(y / 63 * np.pi), 0)
    key = 2.2 * np.exp(-(((x - 32) / 14) ** 2) - ((y - 24) / 11) ** 2)
    fill = 1.0 * np.exp(-(((x - 102) / 22) ** 2) - ((y - 20) / 16) ** 2)
    pixels = np.stack(
        [ambient + key + fill * 0.86, ambient + key * 0.97 + fill * 0.94, ambient + key * 0.91 + fill],
        axis=-1,
    ).astype(np.float32)
    data = vtk.vtkImageData()
    data.SetDimensions(128, 64, 1)
    data.GetPointData().SetScalars(numpy_to_vtk(pixels.reshape(-1, 3), deep=True))
    texture = vtk.vtkTexture()
    texture.SetInputData(data)
    texture.InterpolateOn()
    texture.MipmapOn()
    return texture


def polydata(mesh: trimesh.Trimesh):
    data = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.vertices), deep=True))
    data.SetPoints(points)
    cells = vtk.vtkCellArray()
    cells.SetData(
        numpy_to_vtkIdTypeArray(np.arange(0, 3 * len(mesh.faces) + 1, 3, dtype=np.int64), deep=True),
        numpy_to_vtkIdTypeArray(np.ascontiguousarray(mesh.faces.ravel(), dtype=np.int64), deep=True),
    )
    data.SetPolys(cells)
    normals = numpy_to_vtk(np.ascontiguousarray(mesh.vertex_normals, dtype=np.float32), deep=True)
    data.GetPointData().SetNormals(normals)
    if isinstance(mesh.visual, trimesh.visual.TextureVisuals) and mesh.visual.uv is not None:
        uv = numpy_to_vtk(np.ascontiguousarray(mesh.visual.uv, dtype=np.float32), deep=True)
        uv.SetNumberOfComponents(2)
        data.GetPointData().SetTCoords(uv)
    return data


def actor(mesh: trimesh.Trimesh):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata(mesh))
    item = vtk.vtkActor()
    item.SetMapper(mapper)
    prop = item.GetProperty()
    prop.SetInterpolationToPBR()
    prop.SetMetallic(0.10)
    prop.SetRoughness(0.48)
    prop.SetAmbient(0.12)
    if isinstance(mesh.visual, trimesh.visual.TextureVisuals):
        mat = (
            mesh.visual.material.to_pbr()
            if isinstance(mesh.visual.material, trimesh.visual.material.SimpleMaterial)
            else mesh.visual.material
        )
        rgba = (
            np.asarray(
                mat.baseColorFactor if mat.baseColorFactor is not None else [205, 215, 222, 255], float
            )
            / 255
        )
        prop.SetColor(*rgba[:3])
        prop.SetOpacity(float(rgba[3]))
        prop.SetMetallic(float(mat.metallicFactor if mat.metallicFactor is not None else 0.1))
        prop.SetRoughness(float(mat.roughnessFactor if mat.roughnessFactor is not None else 0.48))
        if mat.baseColorTexture is not None:
            pixels = np.asarray(mat.baseColorTexture.convert("RGB"))[::-1].copy()
            data = vtk.vtkImageData()
            data.SetDimensions(pixels.shape[1], pixels.shape[0], 1)
            data.GetPointData().SetScalars(numpy_to_vtk(pixels.reshape(-1, 3), deep=True))
            texture = vtk.vtkTexture()
            texture.SetInputData(data)
            texture.InterpolateOn()
            texture.UseSRGBColorSpaceOn()
            prop.SetBaseColorTexture(texture)
            prop.SetColor(1, 1, 1)
    else:
        rgb = np.asarray(mesh.visual.vertex_colors[:, :3]).mean(axis=0) / 255
        prop.SetColor(*rgb)
    return item


def render(scene: trimesh.Scene, position, look_at, size=(1280, 900), fov=42.0, up=(0, 0, 1)) -> Image.Image:
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.88, 0.91, 0.93)
    renderer.SetBackground2(0.98, 0.985, 0.99)
    renderer.GradientBackgroundOn()
    renderer.UseImageBasedLightingOn()
    renderer.UseSphericalHarmonicsOn()
    renderer.SetEnvironmentTexture(studio_texture(), False)
    renderer.GetEnvMapPrefiltered().SetPrefilterLevels(4)
    renderer.GetEnvMapPrefiltered().SetPrefilterMaxSamples(32)
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        renderer.AddActor(actor(mesh))
    camera = renderer.GetActiveCamera()
    camera.SetPosition(*position)
    camera.SetFocalPoint(*look_at)
    camera.SetViewUp(*up)
    camera.SetViewAngle(fov)
    camera.SetClippingRange(0.002, 1000.0)
    aim = np.asarray(look_at)
    radius = max(float(np.linalg.norm(np.asarray(position) - aim)), 0.5)
    for offset, intensity, color in [
        ((1, -1.3, 2), 0.85, (1.0, 0.97, 0.91)),
        ((-1, -0.3, 1.2), 0.65, (0.85, 0.93, 1.0)),
        ((0, 1, 1.8), 0.70, (1.0, 1.0, 1.0)),
    ]:
        light = vtk.vtkLight()
        light.SetLightTypeToSceneLight()
        light.SetPosition(*(aim + np.asarray(offset) * radius))
        light.SetFocalPoint(*aim)
        light.SetIntensity(intensity)
        light.SetColor(*color)
        renderer.AddLight(light)
    # Explicit OSMesa prevents VTK's automatic EGL device probing from creating
    # an unauthorized hardware context before the renderer can be checked.
    window = vtk.vtkOSOpenGLRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(*size)
    window.SetMultiSamples(0)
    window.AddRenderer(renderer)
    shadows = vtk.vtkShadowMapPass()
    shadows.GetShadowMapBakerPass().SetResolution(1024)
    passes = vtk.vtkRenderPassCollection()
    passes.AddItem(shadows.GetShadowMapBakerPass())
    passes.AddItem(shadows)
    sequence = vtk.vtkSequencePass()
    sequence.SetPasses(passes)
    camera_pass = vtk.vtkCameraPass()
    camera_pass.SetDelegatePass(sequence)
    renderer.SetPass(camera_pass)
    window.Render()
    capabilities = window.ReportCapabilities()
    if "llvmpipe" not in capabilities.lower() and "softpipe" not in capabilities.lower():
        window.Finalize()
        raise RuntimeError("A verified CPU OpenGL renderer is required: " + capabilities)
    print(capabilities, flush=True)
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGB()
    capture.ReadFrontBufferOff()
    capture.Update()
    image = capture.GetOutput()
    width, height, _ = image.GetDimensions()
    pixels = vtk_to_numpy(image.GetPointData().GetScalars()).reshape(height, width, 3)[::-1].copy()
    window.Finalize()
    return Image.fromarray(pixels)
