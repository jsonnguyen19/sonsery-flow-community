window.__RUNCTX__ = window.__RUNCTX__ || {};

// ============================================================
// PAYLOAD WATCHER
// ============================================================
// Main entry: detect stable payload in latest assistant message,
// handle switch payloads, copy to clipboard, track usage.
//
// Detection  -> PayloadDetector (services/payload-detector.js)
// Stability  -> PayloadStability (services/payload-stability.js)

window.__RUNCTX__.PayloadWatcher = {
  async copyPayloadIfNeeded({
    getState,
    setState,
    onSwitch,
    hasProcessed,
    markProcessed,
    computeKey,
  }) {
    const state = getState();
    if (!state.enabled) return;

    const payload = window.__RUNCTX__.PayloadDetector.getLastPayloadBlock();
    if (!payload) {
      window.__RUNCTX__.PayloadStability.resetPendingPayload();
      return;
    }

    // Dedup key: prefer id (unique), fall back to content hash.
    // The per-tab queue remembers the last 100 keys -> no false positives when
    // the user switches chats or moves between tabs (old DOM payloads are
    // already marked).
    const payloadId = window.__RUNCTX__.PayloadDetector.getPayloadId(payload);
    const payloadKey = computeKey(payload, payloadId);

    if (hasProcessed(payloadKey)) {
      return;
    }

    const stablePayload = window.__RUNCTX__.PayloadStability.trackStablePayload(payload);
    if (!stablePayload) {
      return;
    }

    // Re-check against the stable payload
    const stableId = window.__RUNCTX__.PayloadDetector.getPayloadId(stablePayload.payload);
    const stableKey = computeKey(stablePayload.payload, stableId);

    if (hasProcessed(stableKey)) {
      return;
    }

    // Toast the detect IMMEDIATELY when a new payload is caught (after dedup
    // to avoid spam). Includes tool + id to debug whether the extension is
    // catching the payload.
    try {
      if (await window.__RUNCTX__.shouldShowToasts()) {
        let detectedTool = "unknown";
        try {
          const parsedDetect = JSON.parse(stablePayload.payload);
          detectedTool = parsedDetect.tool || parsedDetect.type || "unknown";
        } catch {}
        const idLabel = stableId ? String(stableId) : "no id";
        window.__RUNCTX__.showToast(
          `📦 Payload detected: ${detectedTool} (id: ${idLabel})`,
          "info"
        );
      }
    } catch {}

    const copied = await window.__RUNCTX__.ClipboardTransport.write(stablePayload.payload);
    if (!copied) {
      const showToastsState = await chrome.storage.local.get(["showToasts"]);
      const showToasts = showToastsState.showToasts !== false;
      if (showToasts) {
        window.__RUNCTX__.showToast("Clipboard write failed", "error");
      }
      window.__RUNCTX__.Logger?.error("Payload clipboard write failed", {
        hash: stablePayload.hash,
        length: stablePayload.payload.length,
      });
      return;
    }

    const payloadCount = state.payloadCount + 1;
    const hasId = !!window.__RUNCTX__.PayloadDetector.getPayloadId(stablePayload.payload);

    const shortHash = String(stableKey).slice(0, 8);

    // Sticky in-progress indicator: stays until the matching result arrives.
    // Applies to both manual and automation modes when toasts are enabled.
    if (await window.__RUNCTX__.shouldShowToasts()) {
      window.__RUNCTX__.showStickyToast("runctx-progress", "Processing...", "info");
    }
    const showToastsState2 = await chrome.storage.local.get(["enabled"]);
    const isAutomation = showToastsState2.enabled === true;
    window.__RUNCTX__.Logger?.info("Payload copied after stable wait", {
      key: stableKey,
      hasId,
      length: stablePayload.payload.length,
      baseStableMs: window.__RUNCTX__.PayloadStability.PAYLOAD_STABLE_MS,
      automation: isAutomation,
    });

    // Track token usage
    try {
      chrome.runtime.sendMessage(
        {
          type: "RUNCTX_TRACK_PAYLOAD",
          payload: stablePayload.payload,
          label: hasId ? `Payload (${shortHash})` : "Payload",
        },
        () => {
          if (chrome.runtime.lastError) {
            console.warn("Track payload error:", chrome.runtime.lastError);
          }
        }
      );
    } catch (e) {
      console.warn("Track payload failed:", e);
    }

    markProcessed(stableKey);
    setState({ payloadCount });

    await chrome.storage.local.set({
      payloadCount,
      lastPayloadAt: new Date().toLocaleTimeString(),
    });
  },
};
