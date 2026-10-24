// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import {
  beginEnvironmentLoad,
  beginGlbLoad,
  createCaptureCamera,
  createCaptureJob,
  environmentCaptureStatus,
  gaussianCaptureStatus,
  glbCaptureStatus,
  markCanvasCapture,
} from "./cameraCapture";
import type { GetRenderRequestMessage } from "./WebsocketMessages";

const request = (overrides: Partial<GetRenderRequestMessage> = {}): GetRenderRequestMessage => ({
  type: "GetRenderRequestMessage",
  render_uuid: "camera-a",
  format: "image/png",
  width: 641,
  height: 480,
  quality: 80,
  wxyz: [1, 0, 0, 0],
  position: [0, 0, 0],
  fov: Math.PI / 3,
  near: 0.002,
  far: 100,
  projection_aspect: 4 / 3,
  expected_node_names: ["/model"],
  timeout_s: 0.05,
  transparent_background: false,
  ...overrides,
});
afterEach(() => vi.useRealTimers());

describe("current camera projection", () => {
  it("retains near/far/aspect independent of integer output dimensions", () => {
    const camera = createCaptureCamera(request(), new THREE.Matrix4());
    expect(camera.near).toBe(0.002);
    expect(camera.far).toBe(100);
    expect(camera.aspect).toBe(4 / 3);
    expect(camera.aspect).not.toBe(641 / 480);
    expect(camera.projectionMatrix.elements[5] / camera.projectionMatrix.elements[0]).toBeCloseTo(4 / 3, 12);
    camera.updateMatrixWorld(true);
    // OpenCV +Z forward: a point 5 mm ahead must survive the 2 mm near clip.
    expect(Math.abs(new THREE.Vector3(0, 0, 0.005).project(camera).z)).toBeLessThan(1);
    const old = createCaptureCamera(request({ near: 0.01 }), new THREE.Matrix4());
    old.updateMatrixWorld(true);
    expect(new THREE.Vector3(0, 0, 0.005).project(old).z).toBeLessThan(-1);
  });
  it("applies the world transform and rejects invalid projection", () => {
    const camera = createCaptureCamera(
      request({ position: [1, 2, 3] }),
      new THREE.Matrix4().makeTranslation(2, 3, 4),
    );
    expect(camera.position.toArray()).toEqual([3, 5, 7]);
    expect(() => createCaptureCamera(request({ far: 0.001 }), new THREE.Matrix4())).toThrow();
    expect(() => createCaptureCamera(request({ projection_aspect: NaN }), new THREE.Matrix4())).toThrow();
  });
});

describe("resource readiness", () => {
  it("permits a genuinely empty Gaussian scene without a mounted renderer", () => {
    expect(gaussianCaptureStatus({}, null)).toEqual({ ready: true });
    // Clearing the last group must not depend on a disposed previous sorter.
    expect(gaussianCaptureStatus({}, () => ({ ready: false, error: "disposed" }))).toEqual({ ready: true });
  });
  it("waits for first nonempty Gaussian mount and preserves actual sorter failures", () => {
    const groups = { cue: new Uint32Array(8) };
    expect(gaussianCaptureStatus(groups, null).ready).toBe(false);
    expect(gaussianCaptureStatus(groups, () => ({ ready: false })).ready).toBe(false);
    expect(gaussianCaptureStatus(groups, () => ({ ready: false, error: "WASM failed" })).error).toBe(
      "WASM failed",
    );
    expect(gaussianCaptureStatus(groups, () => ({ ready: true })).ready).toBe(true);
  });

  it("requires this source, retains texture errors even when GLTF onLoad succeeds", () => {
    const first = new Uint8Array([1]);
    const second = new Uint8Array([1]);
    const load = beginGlbLoad(first);
    expect(glbCaptureStatus(first).ready).toBe(false);
    load.ready();
    expect(glbCaptureStatus(first).ready).toBe(true);
    expect(glbCaptureStatus(second).ready).toBe(false);
    load.fail("texture failed");
    load.ready();
    expect(glbCaptureStatus(first)).toMatchObject({ ready: false, error: "texture failed" });
    load.dispose();
    expect(glbCaptureStatus(first).ready).toBe(false);
  });
  it("does not let one duplicate loader or stale cleanup bless a pending decoder", () => {
    const source = new Uint8Array([1]);
    const a = beginGlbLoad(source);
    const b = beginGlbLoad(source);
    a.ready();
    expect(glbCaptureStatus(source).ready).toBe(false);
    a.dispose();
    expect(glbCaptureStatus(source).ready).toBe(false);
    b.ready();
    expect(glbCaptureStatus(source).ready).toBe(true);
    b.dispose();
  });
  it("waits for the current environment to be applied, not the old non-null map", () => {
    const scene = new THREE.Scene();
    const texture = new THREE.Texture();
    const old = beginEnvironmentLoad(scene, new Uint8Array([1]));
    old.loaded(texture);
    scene.environment = texture;
    old.applied(texture);
    expect(environmentCaptureStatus(scene, new Uint8Array([1])).ready).toBe(true);
    const next = beginEnvironmentLoad(scene, new Uint8Array([2]));
    next.applied(texture);
    old.dispose();
    expect(environmentCaptureStatus(scene, new Uint8Array([2])).ready).toBe(false);
    const replacement = new THREE.Texture();
    next.loaded(replacement);
    next.applied(replacement);
    expect(environmentCaptureStatus(scene, new Uint8Array([2])).ready).toBe(false);
    scene.environment = replacement;
    expect(environmentCaptureStatus(scene, new Uint8Array([2])).ready).toBe(true);
    next.fail("HDR decode failed");
    expect(environmentCaptureStatus(scene, new Uint8Array([2])).error).toBe("HDR decode failed");
  });
  it("distinguishes disabled environment from the asynchronously loaded default", () => {
    const scene = new THREE.Scene();
    expect(environmentCaptureStatus(scene, null).ready).toBe(true);
    expect(environmentCaptureStatus(scene, undefined).ready).toBe(false);
    const load = beginEnvironmentLoad(scene, "/default.jpg");
    const texture = new THREE.Texture();
    load.loaded(texture);
    scene.environment = texture;
    load.applied(texture);
    expect(environmentCaptureStatus(scene, undefined).ready).toBe(true);
    expect(environmentCaptureStatus(scene, null).ready).toBe(false);
  });
});

describe("bounded request lifecycle and recording signal", () => {
  it("timeouts with the blocked resource and releases once; drops late encodes", () => {
    vi.useFakeTimers();
    const send = vi.fn();
    const release = vi.fn();
    const job = createCaptureJob(request(), send, release);
    job.waitFor("GLB node/textures /model");
    vi.advanceTimersByTime(51);
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({
      render_uuid: "camera-a",
      error: expect.stringContaining("/model"),
    });
    expect(release).toHaveBeenCalledTimes(1);
    job.respond(new Uint8Array([1]));
    expect(send).toHaveBeenCalledTimes(1);
    expect(job.pending()).toBe(false);
  });
  it("correlates overlapping jobs and clears their own timeout", () => {
    vi.useFakeTimers();
    const send = vi.fn();
    const release = vi.fn();
    const a = createCaptureJob(request(), send, release);
    const b = createCaptureJob(request({ render_uuid: "camera-b" }), send, release);
    b.respond(new Uint8Array([2]));
    a.respond(new Uint8Array([1]));
    vi.advanceTimersByTime(100);
    expect(send.mock.calls.map(([r]) => r.render_uuid)).toEqual(["camera-b", "camera-a"]);
    expect(release).toHaveBeenCalledTimes(2);
  });
  it("signals canvas active/restored explicitly without copying DOM pixels", () => {
    const canvas = document.createElement("canvas");
    const events: string[] = [];
    canvas.addEventListener("viser:camera-capture-active", (event) =>
      events.push((event as CustomEvent).detail.render_uuid),
    );
    canvas.addEventListener("viser:camera-capture-restored", (event) =>
      events.push((event as CustomEvent).detail.render_uuid),
    );
    markCanvasCapture(canvas, "a", true);
    expect(canvas.dataset.viserCameraCaptureActive).toBe("true");
    markCanvasCapture(canvas, "a", false);
    expect(canvas.dataset.viserCameraCaptureActive).toBe("false");
    expect(events).toEqual(["a", "a"]);
  });
});
