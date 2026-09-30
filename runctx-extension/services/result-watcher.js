window.__RUNCTX__ = window.__RUNCTX__ || {};

// Per-result toast state keyed by result hash. Used to avoid spamming the
// "consume failed" warning for the same result on every tick. The sticky
// "Processing..." toast is driven from payload-watcher and dismissed here
// once the matching result arrives.
window.__RUNCTX__.resultToastState = window.__RUNCTX__.resultToastState || {
  hash: "",
  consumeWarned: false,
};

function resetResultToastStateIfNeeded(hash) {
  const st = window.__RUNCTX__.resultToastState;
  if (!hash || st.hash !== hash) {
    window.__RUNCTX__.resultToastState = {
      hash: hash || "",
      consumeWarned: false,
    };
  }
}

async function getResultFromBridge() {
  const bridgeResult = await window.__RUNCTX__.HttpBridgeTransport.getResult();

  if (bridgeResult?.result) {
    return {
      source: "bridge",
      text: bridgeResult.result,
      hash: bridgeResult.hash || "",
    };
  }

  return null;
}

let _lastInjectedResultHash = "";

// Number of consecutive injection failures for the current result.
// Some editors need a moment before they accept input, so the
// first tick can fail and the next one succeeds. We retry silently and only
// warn the user after several consecutive failures.
let _injectFailCount = 0;
const INJECT_FAIL_TOAST_THRESHOLD = 3;

window.__RUNCTX__.ResultWatcher = {
  async pasteResultIfNeeded({ getState }) {
    const logger = window.__RUNCTX__.Logger;
    const state = getState();

    const result = await getResultFromBridge();
    if (!result?.text) {
      return;
    }

    // Deduplicate: skip if same result hash already injected
    if (result.hash && result.hash === _lastInjectedResultHash) {
      return;
    }

    const trimmed = window.__RUNCTX__.HashUtils.cleanCodeBlock(result.text);
    // Check if it's valid JSON with success/error structure
    try {
      const parsed = JSON.parse(trimmed);
      if (typeof parsed.success !== "boolean") {
        throw new Error("Missing success field");
      }
      // Valid new format
    } catch {
      // Check for old format
      if (!trimmed.startsWith("RUNCTX_RESULT")) {
        if (await window.__RUNCTX__.shouldShowToasts()) {
          window.__RUNCTX__.showToast("⚠️ Invalid result format", "warn");
        }
        return;
      }
    }

    // Reset per-result toast state when a new result hash arrives.
    resetResultToastStateIfNeeded(result.hash);

    // Manual mode: result is ready, user pastes it themselves.
    // Dismiss sticky progress, show toast, and consume to avoid repeated toasts.
    if (!state.enabled) {
      if (await window.__RUNCTX__.shouldShowToasts()) {
        window.__RUNCTX__.hideStickyToast("runctx-progress");
        window.__RUNCTX__.showToast("📥 Result received", "success");
      }
      window.__RUNCTX__.playResultSound();
      // Consume result in manual mode to prevent repeated detection
      await window.__RUNCTX__.HttpBridgeTransport.consumeResult();
      // Update counters
      await chrome.storage.local.set({
        resultCount: state.resultCount + 1,
        lastResultAt: new Date().toLocaleTimeString(),
      });
      // Mark as processed to prevent re-detection
      if (result.hash) {
        _lastInjectedResultHash = result.hash;
      }
      return;
    }

    // Automation mode
    logger.info("New result detected", {
      source: result.source,
      length: trimmed.length,
    });

    const resultCount = state.resultCount + 1;

    let injected = false;

    try {
      injected = window.__RUNCTX__.DomTransport.inject(trimmed);
      logger.info("DOM inject finished", { injected });
    } catch (error) {
      logger.error("DOM inject crashed", error);
    }

    if (!injected) {
      try {
        injected = window.__RUNCTX__.AdapterRegistry.pasteTextToChat(trimmed);
        logger.warn("Fallback paste attempted", { injected });
      } catch (error) {
        logger.error("Fallback paste crashed", error);
      }
    }

    if (!injected) {
      _injectFailCount += 1;
      logger.error("Result injection failed: chat input not found or rejected", {
        failCount: _injectFailCount,
      });
      // Only toast after several consecutive failures. Editors that need a
      // moment to become ready will succeed on a later tick, so a single
      // failure is not worth alarming the user about.
      if (_injectFailCount >= INJECT_FAIL_TOAST_THRESHOLD) {
        if (await window.__RUNCTX__.shouldShowToasts()) {
          window.__RUNCTX__.showToast("❌ Cannot find chat input", "error");
        }
        _injectFailCount = 0;
      }
      return;
    }

    // Injection succeeded: reset the failure counter.
    _injectFailCount = 0;

    // Result has arrived: dismiss the sticky "Processing..." indicator and
    // show the normal result toast (respects shouldShowToasts).
    if (await window.__RUNCTX__.shouldShowToasts()) {
      window.__RUNCTX__.hideStickyToast("runctx-progress");
      window.__RUNCTX__.showToast("📥 Result received", "success");
    }
    window.__RUNCTX__.playResultSound();

    // Track token usage
    try {
      chrome.runtime.sendMessage(
        {
          type: "RUNCTX_TRACK_RESULT",
          result: trimmed,
          label: "Result from bridge",
        },
        () => {
          if (chrome.runtime.lastError) {
            console.warn("Track result error:", chrome.runtime.lastError);
          }
        }
      );
    } catch (e) {
      console.warn("Track result failed:", e);
    }

    // Mark as injected in-memory IMMEDIATELY to prevent re-injection on next tick
    if (result.hash) {
      _lastInjectedResultHash = result.hash;
    }

    // Consume the result only after successful injection.
    // Only warn ONCE per result hash so an un-consumable result does not
    // spam this toast on every tick.
    const consumed = await window.__RUNCTX__.HttpBridgeTransport.consumeResult();
    if (consumed) {
      await chrome.storage.local.set({
        resultCount,
        lastResultAt: new Date().toLocaleTimeString(),
      });
    } else {
      const st = window.__RUNCTX__.resultToastState;
      if (!st.consumeWarned) {
        st.consumeWarned = true;
        if (await window.__RUNCTX__.shouldShowToasts()) {
          window.__RUNCTX__.showToast("⚠️ Failed to consume result - will retry", "warn");
        }
      }
    }

    if (injected) {
      // Delay before auto-send to space out requests → reduce rate limiting.
      // Base delay comes from speed-config, scaled by the current speedMode.
      // veryFast (factor 0) -> scaledDelayMs = 0 -> bypass, send immediately.
      const baseDelayMs = window.__RUNCTX_SPEED__?.RESULT_TO_SEND_BASE_MS ?? 800;
      const scaledDelayMs = window.__RUNCTX__.Speed?.scale(baseDelayMs) ?? baseDelayMs;
      logger.info("Auto send scheduled", { baseDelayMs, scaledDelayMs });

      const doSend = async () => {
        try {
          const sent = await window.__RUNCTX__.AdapterRegistry.clickSendButtonWhenReady();
          logger.info("Auto send finished", { sent });
          if (!sent) {
            if (await window.__RUNCTX__.shouldShowToasts()) {
              window.__RUNCTX__.showToast("⚠️ Send button not found", "warn");
            }
          }
        } catch (error) {
          logger.error("Auto send crashed", error);
        }
      };

      if (scaledDelayMs <= 0) {
        // Bypass: call async without awaiting (keep the non-blocking semantics).
        doSend();
      } else {
        setTimeout(doSend, scaledDelayMs);
      }
    }
  },
};
