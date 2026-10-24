/* Inject with page.evaluate(source), then call
 * window.__holocueRuntimeCameraRecording.start(options) / stop().
 * Only completed interactive WebGL frames are copied. This does not render,
 * capture the DOM, change the camera, or advance the simulation clock.
 */
(() => {
  const name = "__holocueRuntimeCameraRecording";
  const version = 4;
  if (window[name]?.version === version) return { installed: true, version };
  if (window[name]) {
    const previous = window[name].status();
    if (previous && !previous.stopped) {
      throw new Error("Stop the previous recorder before replacing its implementation.");
    }
  }

  const activeEvent = "viser:camera-capture-active";
  const restoredEvent = "viser:camera-capture-restored";
  let current = null;
  let lastSummary = null;
  let lastResult = null;
  let resultRetrieved = true;

  const timestamp = () => {
    const now = performance.now();
    return { performance_ms: now, epoch_ms: performance.timeOrigin + now };
  };
  const errorText = (error) => (error instanceof Error ? `${error.name}: ${error.message}` : String(error));

  function resolutionInfo(renderer) {
    return {
      ...timestamp(),
      renderer_pixel_ratio: renderer.getPixelRatio(),
      window_device_pixel_ratio: window.devicePixelRatio,
      fixed_dpr_setting: window.__viserTestpoints?.devSettings?.get()?.fixedDpr ?? null,
      canvas_width: renderer.domElement.width,
      canvas_height: renderer.domElement.height,
      canvas_css_width: renderer.domElement.clientWidth,
      canvas_css_height: renderer.domElement.clientHeight,
    };
  }

  function gpuInfo(renderer) {
    const gl = renderer.getContext();
    const extension = gl.getExtension("WEBGL_debug_renderer_info");
    return {
      vendor: gl.getParameter(gl.VENDOR),
      renderer: gl.getParameter(gl.RENDERER),
      unmasked_vendor: extension ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL) : null,
      unmasked_renderer: extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : null,
      version: gl.getParameter(gl.VERSION),
      shading_language_version: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
      context_attributes: gl.getContextAttributes(),
      resolution: resolutionInfo(renderer),
    };
  }

  function beginGap(state, uuid) {
    if (!state.gap) {
      state.gap = {
        reason: "virtual_camera_capture",
        started: timestamp(),
        ended: null,
        render_uuids: [],
      };
      state.skippedIntervals.push(state.gap);
    }
    if (uuid && !state.gap.render_uuids.includes(uuid)) {
      state.gap.render_uuids.push(uuid);
    }
  }

  function endGap(state) {
    if (!state.gap) return;
    state.gap.ended = timestamp();
    state.gap.duration_ms = state.gap.ended.performance_ms - state.gap.started.performance_ms;
    state.gap = null;
  }

  function detach(state) {
    clearTimeout(state.readyTimer);
    state.canvas.removeEventListener(activeEvent, state.onActive);
    state.canvas.removeEventListener(restoredEvent, state.onRestored);
    state.canvas.removeEventListener("webglcontextlost", state.onContextLost);
    if (state.scene.onAfterRender === state.hook) {
      state.scene.onAfterRender = state.previousHook;
      state.hookRestored = true;
    } else {
      state.hookRestored = false;
      state.errors.push("Scene onAfterRender changed during recording; not overwritten.");
    }
  }

  function release(state) {
    for (const track of state.stream?.getTracks() ?? []) track.stop();
    if (state.recordingCanvas) {
      state.recordingCanvas.width = 0;
      state.recordingCanvas.height = 0;
      state.recordingCanvas.remove();
    }
    state.recordingCanvas = null;
    state.context = null;
    state.stream = null;
    state.track = null;
  }

  function summary(state) {
    return {
      ok: state.errors.length === 0 && state.copiedFrames > 0,
      source: "viser_interactive_webgl_canvas",
      timing: "real_time_variable_frame_rate",
      alpha_composite_background: "#ffffff",
      requested_max_fps: state.fps,
      width: state.width,
      height: state.height,
      mime_type: state.recorder?.mimeType ?? state.mimeType,
      video_bits_per_second: state.recorder?.videoBitsPerSecond ?? state.bitrate,
      requested: state.requested,
      started: state.started,
      stopped: state.stopped,
      wall_duration_seconds:
        state.started && state.stopped
          ? (state.stopped.performance_ms - state.started.performance_ms) / 1000
          : null,
      first_copied_frame: state.firstCopied,
      last_copied_frame: state.lastCopied,
      actual_copied_frames: state.copiedFrames,
      rate_limited_normal_frames: state.rateLimited,
      rejected_virtual_or_offscreen_frames: state.rejectedFrames,
      copied_frame_times_ms: state.frameTimes,
      skipped_intervals: state.skippedIntervals,
      invalid_frames: state.invalidFrames,
      media_events: state.mediaEvents,
      gl: state.gl,
      gl_at_stop: state.glAtStop,
      hook_restored: state.hookRestored,
      errors: [...state.errors],
      byte_length: state.byteLength ?? null,
    };
  }

  function toBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error ?? new Error("Blob read failed"));
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
      reader.readAsDataURL(blob);
    });
  }

  async function finish(state) {
    if (state.finishing) return;
    state.finishing = true;
    clearTimeout(state.stopTimer);
    const blob = new Blob(state.chunks, {
      type: state.recorder?.mimeType ?? state.mimeType,
    });
    state.byteLength = blob.size;
    if (!blob.size) state.errors.push("Recorder returned an empty video.");
    let base64 = null;
    try {
      base64 = await toBase64(blob);
    } catch (error) {
      state.errors.push(errorText(error));
    } finally {
      release(state);
      state.chunks.length = 0;
      if (current === state) current = null;
    }
    lastSummary = summary(state);
    // Retain one completed result, including failures, until the caller takes it.
    // Auto-stop must not discard the only video when no stop() is awaiting it.
    lastResult = { ...lastSummary, base64 };
    state.resolveStop(lastResult);
  }

  function stopState(state, error = null) {
    if (error) state.errors.push(errorText(error));
    if (state.stopping) return state.stopPromise;
    state.stopping = true;
    state.stopped = timestamp();
    if (state.renderer) {
      try {
        state.glAtStop = gpuInfo(state.renderer);
      } catch (failure) {
        state.errors.push(errorText(failure));
      }
    }
    endGap(state);
    detach(state);
    if (!state.startSettled) {
      state.startSettled = true;
      state.rejectStart(new Error(state.errors[0] ?? "Stopped before the first recorded frame."));
    }
    if (state.recorderStarted) {
      state.stopTimer = setTimeout(() => {
        state.errors.push("Timed out waiting for the final MediaRecorder data/stop event.");
        void finish(state);
      }, 10000);
      try {
        // An error may set state=inactive before its final data/stop events.
        if (state.recorder.state !== "inactive") state.recorder.stop();
      } catch (failure) {
        state.errors.push(errorText(failure));
        void finish(state);
      }
    } else {
      void finish(state);
    }
    return state.stopPromise;
  }

  function initializeRecorder(state, renderer) {
    if (renderer.domElement !== state.canvas) {
      throw new Error("The completed render did not use the selected Viser canvas.");
    }
    state.width = state.canvas.width;
    state.height = state.canvas.height;
    if (!state.width || !state.height || renderer.getContext().isContextLost()) {
      throw new Error("Viser canvas has no valid completed WebGL frame.");
    }
    state.gl = gpuInfo(renderer);
    state.renderer = renderer;
    state.recordingCanvas = document.createElement("canvas");
    state.recordingCanvas.width = state.width;
    state.recordingCanvas.height = state.height;
    state.context = state.recordingCanvas.getContext("2d", { alpha: false });
    if (!state.context) throw new Error("Cannot create the video copy canvas.");
    state.stream = state.recordingCanvas.captureStream(0);
    state.track = state.stream.getVideoTracks()[0];
    if (!state.track || typeof state.track.requestFrame !== "function") {
      throw new Error("CanvasCaptureMediaStreamTrack.requestFrame is unavailable.");
    }
    for (const type of ["mute", "unmute", "ended"]) {
      state.track.addEventListener(type, () => {
        state.mediaEvents.push({ type: `track_${type}`, ...timestamp() });
        if (!state.stopping && (type === "mute" || type === "ended")) {
          void stopState(state, new Error(`Recording track became ${type}.`));
        }
      });
    }
    state.recorder = new MediaRecorder(state.stream, {
      mimeType: state.mimeType,
      videoBitsPerSecond: state.bitrate,
    });
    state.recorder.ondataavailable = (event) => {
      state.mediaEvents.push({ type: "data", bytes: event.data.size, ...timestamp() });
      if (event.data.size) state.chunks.push(event.data);
    };
    state.recorder.onerror = (event) => {
      void stopState(state, event.error ?? new Error("MediaRecorder failed."));
    };
    state.recorder.onstop = () => {
      state.mediaEvents.push({ type: "stop", ...timestamp() });
      if (!state.stopping) {
        state.errors.push("MediaRecorder stopped without an explicit stop request.");
        state.stopping = true;
        state.stopped = timestamp();
        try {
          state.glAtStop = gpuInfo(state.renderer);
        } catch (failure) {
          state.errors.push(errorText(failure));
        }
        endGap(state);
        detach(state);
        if (!state.startSettled) {
          state.startSettled = true;
          state.rejectStart(new Error(state.errors[0]));
        }
      }
      void finish(state);
    };
    state.recorder.onstart = () => {
      state.mediaEvents.push({ type: "start", ...timestamp() });
      if (state.stopping || state.startSettled) return;
      if (!state.copiedFrames) {
        void stopState(state, new Error("No completed scene frame was copied at start."));
        return;
      }
      clearTimeout(state.readyTimer);
      state.startSettled = true;
      state.resolveStart(summary(state));
    };
    state.started = timestamp();
    state.recorder.start(1000);
    state.recorderStarted = true;
  }

  function copyCompletedFrame(state, renderer) {
    if (!state.recorder) initializeRecorder(state, renderer);
    if (state.canvas.width !== state.width || state.canvas.height !== state.height) {
      const invalid = {
        ...timestamp(),
        expected_width: state.width,
        expected_height: state.height,
        actual_width: state.canvas.width,
        actual_height: state.canvas.height,
        capture_active: state.canvas.dataset.viserCameraCaptureActive ?? null,
        capture_uuid: state.canvas.dataset.viserCameraCaptureUuid ?? null,
        render_target_is_null: renderer.getRenderTarget() === null,
        renderer_canvas_is_source: renderer.domElement === state.canvas,
        camera_is_interactive: true,
        resolution: resolutionInfo(renderer),
      };
      state.invalidFrames.push(invalid);
      throw new Error(`Normal Viser canvas dimensions changed during recording: ${JSON.stringify(invalid)}`);
    }
    state.context.fillStyle = "#ffffff";
    state.context.fillRect(0, 0, state.width, state.height);
    state.context.drawImage(state.canvas, 0, 0);
    state.track.requestFrame();
    const copied = timestamp();
    state.firstCopied ??= copied;
    state.lastCopied = copied;
    state.copiedFrames += 1;
    state.frameTimes.push(copied.performance_ms - state.started.performance_ms);
  }

  async function start(options = {}) {
    if (current) throw new Error("A camera recording is already active or finishing.");
    if (lastResult && !resultRetrieved) {
      throw new Error("Retrieve the previous recording with stop() before starting another.");
    }
    const mutable = window.__viserMutable;
    if (!mutable?.canvas || !mutable.scene || !mutable.camera) {
      throw new Error("Viser canvas, scene and camera must already exist.");
    }
    const fps = options.maxFps ?? 15;
    const bitrate = options.videoBitsPerSecond ?? 4000000;
    const readyTimeoutMs = options.readyTimeoutMs ?? 10000;
    const mimeType = options.mimeType ?? "video/webm;codecs=vp8";
    if (!Number.isFinite(fps) || fps <= 0 || fps > 15) {
      throw new Error("maxFps must be finite, positive, and at most 15.");
    }
    if (!Number.isInteger(bitrate) || bitrate <= 0) throw new Error("Invalid video bitrate.");
    if (!Number.isFinite(readyTimeoutMs) || readyTimeoutMs <= 0) {
      throw new Error("readyTimeoutMs must be finite and positive.");
    }
    if (!mimeType.startsWith("video/webm") || !MediaRecorder.isTypeSupported(mimeType)) {
      throw new Error(`Unsupported WebM MIME type: ${mimeType}`);
    }
    const state = {
      mutable,
      canvas: mutable.canvas,
      scene: mutable.scene,
      fps,
      bitrate,
      mimeType,
      requested: timestamp(),
      started: null,
      stopped: null,
      width: null,
      height: null,
      gl: null,
      glAtStop: null,
      renderer: null,
      recorder: null,
      recordingCanvas: null,
      context: null,
      stream: null,
      track: null,
      chunks: [],
      frameTimes: [],
      copiedFrames: 0,
      rateLimited: 0,
      rejectedFrames: 0,
      firstCopied: null,
      lastCopied: null,
      gap: null,
      skippedIntervals: [],
      invalidFrames: [],
      mediaEvents: [],
      errors: [],
      stopping: false,
      finishing: false,
      startSettled: false,
      hookRestored: null,
      recorderStarted: false,
      previousHook: mutable.scene.onAfterRender,
    };
    const ready = new Promise((resolve, reject) => {
      state.resolveStart = resolve;
      state.rejectStart = reject;
    });
    state.stopPromise = new Promise((resolve) => {
      state.resolveStop = resolve;
    });
    state.onActive = (event) => beginGap(state, event.detail?.render_uuid);
    state.onRestored = () => endGap(state);
    state.onContextLost = () => {
      void stopState(state, new Error("WebGL context lost."));
    };
    state.hook = function (renderer, scene, camera) {
      try {
        if (typeof state.previousHook === "function") state.previousHook.apply(this, arguments);
      } catch (error) {
        void stopState(state, error);
        throw error;
      }
      if (current !== state || state.stopping) return;
      if (state.canvas.dataset.viserCameraCaptureActive === "true") {
        beginGap(state, state.canvas.dataset.viserCameraCaptureUuid);
        state.rejectedFrames += 1;
        return;
      }
      if (scene !== state.scene || camera !== state.mutable.camera || renderer.getRenderTarget() !== null) {
        state.rejectedFrames += 1;
        return;
      }
      if (state.lastCopied && performance.now() - state.lastCopied.performance_ms < 1000 / state.fps) {
        state.rateLimited += 1;
        return;
      }
      try {
        copyCompletedFrame(state, renderer);
      } catch (error) {
        void stopState(state, error);
      }
    };
    current = state;
    lastResult = null;
    resultRetrieved = false;
    state.canvas.addEventListener(activeEvent, state.onActive);
    state.canvas.addEventListener(restoredEvent, state.onRestored);
    state.canvas.addEventListener("webglcontextlost", state.onContextLost);
    state.scene.onAfterRender = state.hook;
    state.readyTimer = setTimeout(() => {
      void stopState(state, new Error("Timed out waiting for the first completed normal Viser frame."));
    }, readyTimeoutMs);
    if (state.canvas.dataset.viserCameraCaptureActive === "true") {
      beginGap(state, state.canvas.dataset.viserCameraCaptureUuid);
    }
    // Wait for an existing normal render; do not synthesize a first frame.
    return ready;
  }

  window[name] = {
    version,
    start,
    async stop() {
      if (!current && !lastResult) throw new Error("No camera recording is active or retained.");
      const result = current ? await stopState(current) : lastResult;
      resultRetrieved = true;
      return result;
    },
    status() {
      return current ? summary(current) : lastSummary;
    },
  };
  return { installed: true, version };
})();
