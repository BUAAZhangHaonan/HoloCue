// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import * as THREE from "three";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { glbCaptureStatus } from "./cameraCapture";
import { useGlbLoader } from "./mesh/GlbLoaderUtils";

const mocks = vi.hoisted(() => ({ loads: [] as any[] }));
vi.mock("three-stdlib", () => ({
  DRACOLoader: class {
    setDecoderPath() {}
  },
  GLTFLoader: class {
    constructor(private manager: any) {}
    setDRACOLoader() {}
    parse(data: ArrayBuffer, _path: string, loaded: (result: any) => void, failed: (error: any) => void) {
      mocks.loads.push({ manager: this.manager, loaded, failed, data });
    }
  },
}));

function Probe({ source }: { source: Uint8Array }) {
  const result = useGlbLoader(source);
  return React.createElement("div", {}, result.gltf ? "loaded" : "pending");
}
let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.loads.length = 0;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

it("real LoadingManager texture errors cannot become capture-ready when GLTF onLoad follows", async () => {
  const source = new Uint8Array([1]);
  await act(async () => root.render(React.createElement(Probe, { source })));
  expect(glbCaptureStatus(source).ready).toBe(false);
  const load = mocks.loads[0];
  expect(load.manager).toBeInstanceOf(THREE.LoadingManager);
  await act(async () => {
    load.manager.itemError("missing.png");
    load.loaded({ scene: new THREE.Group(), animations: [] });
  });
  expect(container.textContent).toBe("loaded");
  expect(glbCaptureStatus(source)).toMatchObject({
    ready: false,
    error: expect.stringContaining("missing.png"),
  });
});

it("a late previous GLB parse cannot satisfy or dispose the replacement load", async () => {
  const source = new Uint8Array([1]);
  const replacement = new Uint8Array([2]);
  await act(async () => root.render(React.createElement(Probe, { source })));
  const previous = mocks.loads[0];
  await act(async () => root.render(React.createElement(Probe, { source: replacement })));
  await act(async () => previous.loaded({ scene: new THREE.Group(), animations: [] }));
  expect(container.textContent).toBe("pending");
  expect(glbCaptureStatus(replacement).ready).toBe(false);
  await act(async () => mocks.loads[1].loaded({ scene: new THREE.Group(), animations: [] }));
  expect(container.textContent).toBe("loaded");
  expect(glbCaptureStatus(replacement).ready).toBe(true);
  expect(glbCaptureStatus(source).ready).toBe(false);
});
