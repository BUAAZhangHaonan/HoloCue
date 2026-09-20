import { expect, test } from "vitest";
import { createGaussianMeshProps } from "./GaussianSplatsHelpers";

test("the real Gaussian quad has a finite three-dimensional bounding sphere", () => {
  const props = createGaussianMeshProps(new Uint32Array(16), 1, 4096);
  props.geometry.computeBoundingSphere();
  const sphere = props.geometry.boundingSphere!;
  expect(sphere.center.toArray().every(Number.isFinite)).toBe(true);
  expect(sphere.radius).toBeCloseTo(Math.sqrt(8));
  expect(props.geometry.getAttribute("position").itemSize).toBe(3);
  expect(props.geometry.getAttribute("position").count).toBe(4);
  props.geometry.dispose();
  props.material.dispose();
  props.textureBuffer.dispose();
  props.textureT_camera_groups.dispose();
});
