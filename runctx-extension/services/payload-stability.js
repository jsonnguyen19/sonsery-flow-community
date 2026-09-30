window.__RUNCTX__ = window.__RUNCTX__ || {};

// ============================================================
// PAYLOAD STABILITY TRACKER
// ============================================================
// Track pending payload and wait until it is stable (not changing)
// before deciding to copy it.

const PAYLOAD_STABLE_MS = 300;
const PAYLOAD_STABLE_MIN_MS = 200;

function scaledStableMs() {
  return window.__RUNCTX__.Speed?.scale(PAYLOAD_STABLE_MS) ?? PAYLOAD_STABLE_MS;
}
function scaledStableMinMs() {
  return window.__RUNCTX__.Speed?.scale(PAYLOAD_STABLE_MIN_MS) ?? PAYLOAD_STABLE_MIN_MS;
}

let pendingPayload = "";
let pendingPayloadHash = "";
let pendingPayloadFirstSeenAt = 0;

function isValidJson(text) {
  try {
    JSON.parse(text);
    return true;
  } catch {
    return false;
  }
}

function resetPendingPayload() {
  pendingPayload = "";
  pendingPayloadHash = "";
  pendingPayloadFirstSeenAt = 0;
}

function trackStablePayload(payload) {
  const hash = window.__RUNCTX__.HashUtils.hashText(payload);
  const now = Date.now();

  if (hash !== pendingPayloadHash) {
    pendingPayload = payload;
    pendingPayloadHash = hash;
    pendingPayloadFirstSeenAt = now;
    window.__RUNCTX__.Logger?.debug("Payload candidate changed. Waiting for stable copy...", {
      hash,
      length: payload.length,
    });
    return null;
  }

  const elapsed = now - pendingPayloadFirstSeenAt;
  const stableMs = scaledStableMs();
  const stableMinMs = scaledStableMinMs();

  // EARLY DETECTION: if JSON is valid and stable for min time, copy immediately
  if (isValidJson(pendingPayload) && elapsed >= stableMinMs) {
    window.__RUNCTX__.Logger?.debug("Payload stable (early detection)", {
      elapsedMs: elapsed,
      hash,
      length: pendingPayload.length,
    });
    return {
      payload: pendingPayload,
      hash: pendingPayloadHash,
    };
  }

  // Fallback: wait for max time
  if (elapsed >= stableMs) {
    if (isValidJson(pendingPayload)) {
      window.__RUNCTX__.Logger?.debug("Payload stable (max timeout)", {
        elapsedMs: elapsed,
        hash,
        length: pendingPayload.length,
      });
      return {
        payload: pendingPayload,
        hash: pendingPayloadHash,
      };
    }
    window.__RUNCTX__.Logger?.debug("Invalid JSON after max timeout, resetting");
    resetPendingPayload();
    return null;
  }

  return null;
}

window.__RUNCTX__.PayloadStability = {
  PAYLOAD_STABLE_MS,
  PAYLOAD_STABLE_MIN_MS,
  isValidJson,
  resetPendingPayload,
  trackStablePayload,
};
