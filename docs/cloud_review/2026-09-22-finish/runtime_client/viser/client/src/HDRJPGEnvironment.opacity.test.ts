// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import * as THREE from "three";
import { ViewerContext } from "./ViewerContext";
import { HDRJPGEnvironment } from "./HDRJPGEnvironment";

// The component only consumes requestRender; the real context module imports
// unrelated UI styles that are outside this isolated component regression.
vi.mock("./ViewerContext", async () => {
  const ReactModule = await import("react");
  return { ViewerContext: ReactModule.createContext<any>(null) };
});

const harness = vi.hoisted(() => ({
  state: {} as any,
  frame: (() => {}) as () => void,
  loads: [] as Array<(result: any) => void>,
}));
vi.mock("@react-three/fiber", () => ({
  useThree: (selector: (state: any) => any) => selector(harness.state),
  useFrame: (callback: () => void) => { harness.frame = callback; },
}));
vi.mock("@monogrid/gainmap-js", () => ({
  HDRJPGLoader: class {
    load(_url: string, onLoad: (result: any) => void) { harness.loads.push(onLoad); }
  },
}));

describe("HDR environment canvas opacity", () => {
  let root: Root;
  let canvas: HTMLCanvasElement;
  let viewer: any;
  const render = async (source: string) => {
    await act(async () => {
      root.render(React.createElement(ViewerContext.Provider, { value: viewer },
        React.createElement(HDRJPGEnvironment, { source })));
    });
  };
  const finishLoad = async (index: number) => {
    await act(async () => {
      harness.loads[index]({ renderTarget: { texture: new THREE.Texture(), dispose: vi.fn() } });
    });
  };
  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    canvas = document.createElement("canvas");
    harness.state = { gl: { domElement: canvas }, scene: new THREE.Scene() };
    harness.loads = [];
    viewer = { mutable: { current: { requestRender: vi.fn() } } };
    root = createRoot(document.createElement("div"));
  });
  afterEach(async () => { await act(async () => root.unmount()); });

  it("preserves first-load fade from 0.05 through 0.24 to fully opaque", async () => {
    await render("default-city.jpg");
    expect(Number(canvas.style.opacity)).toBeCloseTo(0.05);
    await finishLoad(0);
    harness.frame();
    expect(Number(canvas.style.opacity)).toBeCloseTo(0.24);
    for (let i = 0; i < 4; i++) harness.frame();
    expect(Number(canvas.style.opacity)).toBe(1);
  });

  it("restores opacity when a second texture loads after only one fade frame", async () => {
    await render("default-city.jpg");
    await finishLoad(0);
    harness.frame();
    expect(Number(canvas.style.opacity)).toBeCloseTo(0.24);
    await render("server-studio.jpg");
    await finishLoad(1);
    expect(Number(canvas.style.opacity)).toBe(1);
    harness.frame();
    expect(Number(canvas.style.opacity)).toBe(1);
  });
});
