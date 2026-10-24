import * as THREE from "three";
import type { GetRenderRequestMessage, GetRenderResponseMessage } from "./WebsocketMessages";

export type CaptureStatus = { ready: boolean; error?: string; waiting?: string };
type LoadState = CaptureStatus;
const glbLoads = new WeakMap<object, Set<LoadState>>();

/** One ticket per real decode, keyed by the exact current message's byte object. */
export function beginGlbLoad(source: object) {
  const state: LoadState = { ready: false };
  const loads = glbLoads.get(source) ?? new Set<LoadState>();
  loads.add(state);
  glbLoads.set(source, loads);
  return {
    ready: () => {
      if (!state.error) state.ready = true;
    },
    fail: (error: unknown) => {
      state.error = String(error);
      state.ready = false;
    },
    dispose: () => {
      loads.delete(state);
      if (loads.size === 0) glbLoads.delete(source);
    },
  };
}

export function glbCaptureStatus(source: object): CaptureStatus {
  const loads = glbLoads.get(source);
  if (!loads?.size) return { ready: false, waiting: "GLB decode has not mounted" };
  for (const state of loads) {
    if (state.error) return { ready: false, error: state.error };
  }
  return { ready: [...loads].every((state) => state.ready), waiting: "GLB or texture decode" };
}

type EnvironmentSource = string | Uint8Array<ArrayBuffer>;
type EnvironmentState = CaptureStatus & { source: EnvironmentSource; texture: THREE.Texture | null };
const environmentLoads = new WeakMap<THREE.Scene, EnvironmentState>();

export function sameEnvironmentSource(a: EnvironmentSource, b: EnvironmentSource): boolean {
  if (a === b) return true;
  if (typeof a === "string" || typeof b === "string") return false;
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

export function beginEnvironmentLoad(scene: THREE.Scene, source: EnvironmentSource) {
  const state: EnvironmentState = { source, texture: null, ready: false };
  environmentLoads.set(scene, state);
  return {
    loaded: (texture: THREE.Texture) => {
      state.texture = texture;
    },
    applied: (texture: THREE.Texture) => {
      if (environmentLoads.get(scene) === state && state.texture === texture && !state.error) {
        state.ready = true;
      }
    },
    fail: (error: unknown) => {
      state.error = String(error);
      state.ready = false;
    },
    dispose: () => {
      if (environmentLoads.get(scene) === state) environmentLoads.delete(scene);
    },
  };
}

/** undefined means the built-in default; null explicitly disables the map. */
export function environmentCaptureStatus(
  scene: THREE.Scene,
  expected: Uint8Array<ArrayBuffer> | null | undefined,
): CaptureStatus {
  if (expected === null) return { ready: scene.environment === null, waiting: "environment removal" };
  const state = environmentLoads.get(scene);
  if (
    !state ||
    (expected === undefined
      ? typeof state.source !== "string"
      : !sameEnvironmentSource(state.source, expected))
  ) {
    return { ready: false, waiting: "current environment decode" };
  }
  if (state.error) return { ready: false, error: state.error };
  return { ready: state.ready && scene.environment === state.texture, waiting: "environment installation" };
}

/** The implementation is intentionally unmounted when there are no Gaussian groups. */
export function gaussianCaptureStatus(
  groupBuffers: Record<string, Uint32Array>,
  rendererStatus: null | (() => CaptureStatus),
): CaptureStatus {
  if (Object.keys(groupBuffers).length === 0) return { ready: true };
  return rendererStatus?.() ?? { ready: false, waiting: "Gaussian renderer mount" };
}

export function createCaptureCamera(request: GetRenderRequestMessage, worldTransform: THREE.Matrix4) {
  const { fov, projection_aspect: aspect, near, far } = request;
  if (
    ![fov, aspect, near, far, ...request.position, ...request.wxyz].every(Number.isFinite) ||
    !(fov > 0 && fov < Math.PI && aspect > 0 && near > 0 && far > near)
  ) {
    throw new Error("Invalid render camera projection");
  }
  const camera = new THREE.PerspectiveCamera(THREE.MathUtils.radToDeg(fov), aspect, near, far);
  camera.position.set(...request.position).applyMatrix4(worldTransform);
  camera.setRotationFromQuaternion(
    new THREE.Quaternion(request.wxyz[1], request.wxyz[2], request.wxyz[3], request.wxyz[0])
      .premultiply(new THREE.Quaternion().setFromRotationMatrix(worldTransform))
      .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI)),
  );
  return camera;
}

/** A timeout also releases the queue in a connected but idle/backgrounded client. */
export function createCaptureJob(
  request: GetRenderRequestMessage,
  send: (response: GetRenderResponseMessage) => void,
  release: () => void,
) {
  let done = false;
  let waiting = "scene commit";
  const deadline = performance.now() + request.timeout_s * 1000;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const respond = (payload: Uint8Array<ArrayBuffer>, error: string | null = null) => {
    if (done) return;
    done = true;
    if (timer !== undefined) clearTimeout(timer);
    release();
    send({ type: "GetRenderResponseMessage", render_uuid: request.render_uuid, payload, error });
  };
  const timeout = () => respond(new Uint8Array(0), `Camera capture timed out awaiting ${waiting}`);
  if (!Number.isFinite(request.timeout_s) || request.timeout_s <= 0) {
    respond(new Uint8Array(0), "Invalid camera capture timeout");
  } else {
    timer = setTimeout(timeout, request.timeout_s * 1000);
  }
  return {
    respond,
    waitFor: (description: string) => {
      waiting = description;
    },
    pending: () => {
      if (!done && performance.now() >= deadline) timeout();
      return !done;
    },
  };
}

export function markCanvasCapture(canvas: HTMLCanvasElement, renderUuid: string, active: boolean) {
  canvas.dataset.viserCameraCaptureActive = String(active);
  canvas.dataset.viserCameraCaptureUuid = renderUuid;
  canvas.dispatchEvent(
    new CustomEvent(active ? "viser:camera-capture-active" : "viser:camera-capture-restored", {
      bubbles: true,
      detail: { render_uuid: renderUuid },
    }),
  );
}
