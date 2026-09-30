// window.__RUNCTX_IS_CONTENT_SCRIPT__ is set by content-marker.js, which
// runs as the first entry of content_scripts[0].js in manifest.json.
const __RUNCTX__ = window.__RUNCTX__;

let enabled = false;
let payloadCount = 0;
let resultCount = 0;
let lastResultHash = "";

// ============================================================
// PROCESSED PAYLOAD QUEUE (per-tab, PERSISTED, FIFO)
// ============================================================
// Dedup by payload id (falls back to a content hash when id is missing).
// Rationale: previously only the last hash was remembered -> when the user
// switched chats (SPA route change) or moved between tabs, an OLD payload in
// the DOM no longer matched the last hash and was reprocessed (switch loop).
//
// The queue stores the last 100 keys, independent of view order / tab.
//
// PERSIST: the queue is synced to `chrome.storage.local` under
// `processedPayloadKeys_<tabId>` so it survives:
//   - F5 / tab reload
//   - Browser close & reopen
//   - Extension reload (content script re-inject)
// `background.js` removes this key when the tab closes (chrome.tabs.onRemoved)
// to avoid leaking storage and to prevent collisions if Chrome reuses tabId.
const PROCESSED_QUEUE_MAX = 100;
const PROCESSED_QUEUE_KEY_PREFIX = "processedPayloadKeys_";
let processedPayloadKeys = new Set();
let processedPayloadKeysLoaded = false;

async function loadState() {
  const state = await chrome.storage.local.get([
    "enabled",
    "payloadCount",
    "resultCount",
    "lastResultHash",
  ]);

  enabled = Boolean(state.enabled);
  payloadCount = Number(state.payloadCount || 0);
  resultCount = Number(state.resultCount || 0);
  lastResultHash = String(state.lastResultHash || "");
}

function getRuntimeState() {
  return {
    enabled,
    payloadCount,
    resultCount,
    lastResultHash,
  };
}

function setRuntimeState(patch) {
  if (Object.prototype.hasOwnProperty.call(patch, "enabled")) enabled = Boolean(patch.enabled);
  if (Object.prototype.hasOwnProperty.call(patch, "payloadCount"))
    payloadCount = Number(patch.payloadCount || 0);
  if (Object.prototype.hasOwnProperty.call(patch, "resultCount"))
    resultCount = Number(patch.resultCount || 0);
  if (Object.prototype.hasOwnProperty.call(patch, "lastResultHash"))
    lastResultHash = String(patch.lastResultHash || "");
}

// Dedup key for a payload: prefer id (unique, timestamp ms).
// Fallback: hash of the payload content if id is missing / invalid.
function computePayloadKey(payload, id) {
  if (id !== null && id !== undefined && /^\d+$/.test(String(id))) {
    return "id:" + String(id);
  }
  return "h:" + __RUNCTX__.HashUtils.hashText(payload);
}

function hasProcessedPayload(key) {
  return processedPayloadKeys.has(key);
}

function markPayloadProcessed(key) {
  if (!key) return;
  if (processedPayloadKeys.has(key)) {
    // Refresh position: delete then re-add so it becomes the "newest" in the
    // Set (Sets keep insertion order -> true LRU-style FIFO eviction).
    processedPayloadKeys.delete(key);
  }
  processedPayloadKeys.add(key);
  while (processedPayloadKeys.size > PROCESSED_QUEUE_MAX) {
    const oldest = processedPayloadKeys.values().next().value;
    processedPayloadKeys.delete(oldest);
  }
  persistProcessedQueue();
}

// Persist the queue to storage.local. Fire-and-forget: do NOT await on the
// tick path to avoid blocking the interval. Errors (invalidated context,
// quota, ...) are only logged — the next mark will overwrite with the latest
// state.
function persistProcessedQueue() {
  if (ownTabId === null || !processedPayloadKeysLoaded) return;
  const key = PROCESSED_QUEUE_KEY_PREFIX + String(ownTabId);
  try {
    chrome.storage.local.set({ [key]: Array.from(processedPayloadKeys) }).catch(() => {
      // context invalidated / quota — ignore, RAM still holds the correct state.
    });
  } catch {
    // chrome.storage undefined (context gone)
  }
}

// Load the queue from storage into RAM. Called once on content script init
// (after ownTabId is known). If ownTabId is not yet available (background has
// not replied), retry briefly.
async function loadProcessedQueue() {
  if (processedPayloadKeysLoaded) return;
  if (ownTabId === null) return;
  const key = PROCESSED_QUEUE_KEY_PREFIX + String(ownTabId);
  try {
    const state = await chrome.storage.local.get([key]);
    const arr = state?.[key];
    if (Array.isArray(arr)) {
      // Only accept strings; drop junk entries if any.
      processedPayloadKeys = new Set(arr.filter((x) => typeof x === "string"));
    }
  } catch {
    // storage failure — treat as an empty queue (safer than crashing).
  }
  processedPayloadKeysLoaded = true;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "RUNCTX_SET_STATE") {
    enabled = Boolean(message.enabled);
    chrome.storage.local.set({ enabled });
    sendResponse({ ok: true, enabled });
    return true;
  }

  if (message?.type === "RUNCTX_GET_STATE") {
    sendResponse({ ok: true, enabled, payloadCount, resultCount });
    return true;
  }

  return false;
});

loadState();

// Exposed on the __RUNCTX__ namespace for other same-context modules.
// Does not break existing logic — only adds a reference on __RUNCTX__.
//
window.__RUNCTX__ = window.__RUNCTX__ || {};

let payloadTickRunning = false;
let resultTickRunning = false;

// Cache own tabId once via background
let ownTabId = null;
try {
  chrome.runtime.sendMessage({ type: "RUNCTX_GET_TAB_ID" }, async (res) => {
    // When the extension has just been reloaded this callback can fire with
    // chrome.runtime.lastError set and res === undefined. Swallow it silently:
    // the orphaned script will be torn down by handleContextInvalidated().
    void chrome.runtime.lastError;
    ownTabId = res?.tabId ?? null;
    // Once tabId is known -> load the persisted queue (if any) from storage.
    // The queue must be ready BEFORE the first tick to avoid re-firing an
    // old payload.
    if (ownTabId !== null) {
      await loadProcessedQueue();
    }
  });
} catch {
  // chrome.runtime already gone — nothing to do here.
}

// Constants (base values, scaled at runtime by the speed factor)
const PAYLOAD_INTERVAL_MS = 700;
const RESULT_INTERVAL_MS = 1000;

function scaledPayloadInterval() {
  return window.__RUNCTX__.Speed?.scale(PAYLOAD_INTERVAL_MS) ?? PAYLOAD_INTERVAL_MS;
}
function scaledResultInterval() {
  return window.__RUNCTX__.Speed?.scale(RESULT_INTERVAL_MS) ?? RESULT_INTERVAL_MS;
}

// Track interval IDs for cleanup
let payloadIntervalId = null;
let resultIntervalId = null;
let isContextValidFlag = true;

function isContextValid() {
  try {
    // Check if chrome.runtime is still accessible
    if (!chrome?.runtime?.id) return false;
    // Try to send a test message to verify context
    return true;
  } catch {
    return false;
  }
}

// Called once when the content script detects that its extension context has
// been invalidated (e.g. the user reloaded the extension). The old content
// script becomes "orphaned": chrome.runtime is gone, so it can never receive
// messages or storage events again. The only clean recovery is to reload the
// page so the freshly reloaded extension re-injects a new content script.
let contextInvalidatedHandled = false;
function handleContextInvalidated() {
  if (contextInvalidatedHandled) return;
  contextInvalidatedHandled = true;
  isContextValidFlag = false;
  stopAllIntervals();
  // Extension was reloaded/updated while this page was open. The old content
  // script is now orphaned (chrome.runtime is gone) and can never recover.
  // We deliberately DO NOT auto-reload the page: the user must manually
  // refresh the tab if they want the extension to re-inject.
  window.__RUNCTX__?.Logger?.debug?.(
    "[content] Extension context invalidated — please reload the page manually to re-init"
  );
}

function stopAllIntervals() {
  if (payloadIntervalId) {
    clearInterval(payloadIntervalId);
    payloadIntervalId = null;
  }
  if (resultIntervalId) {
    clearInterval(resultIntervalId);
    resultIntervalId = null;
  }
}

// setInterval keeps the legacy wall-clock semantics: ticks fire on a fixed
// cadence independent of how long the async watcher takes. The interval is
// scaled by the current speed factor when the interval is created (normal =
// 1.0 -> identical to legacy). Changing speed restarts the intervals with the
// new scaled value.
function startPayloadInterval() {
  payloadIntervalId = setInterval(async () => {
    if (!isContextValid()) {
      handleContextInvalidated();
      return;
    }
    if (payloadTickRunning) return;
    // Wait for the queue to load before the first tick. If ownTabId is not yet
    // available (background replied late), this tick is skipped — the next one
    // runs once the queue is ready. Avoids the race: tick before hydration ->
    // thinks a payload is new -> re-fires it.
    if (!processedPayloadKeysLoaded) {
      if (ownTabId !== null) {
        await loadProcessedQueue();
      }
      if (!processedPayloadKeysLoaded) return;
    }
    payloadTickRunning = true;
    try {
      const pinned = await isPinnedToThisTab();
      if (pinned) {
        await __RUNCTX__.PayloadWatcher.copyPayloadIfNeeded({
          getState: getRuntimeState,
          setState: setRuntimeState,
          hasProcessed: hasProcessedPayload,
          markProcessed: markPayloadProcessed,
          computeKey: computePayloadKey,
        });
      }
    } catch (err) {
      console.error("Payload tick error:", err);
    } finally {
      payloadTickRunning = false;
    }
  }, scaledPayloadInterval());
}

function startResultInterval() {
  resultIntervalId = setInterval(async () => {
    if (!isContextValid()) {
      handleContextInvalidated();
      return;
    }
    if (resultTickRunning) return;
    resultTickRunning = true;
    try {
      const pinned = await isPinnedToThisTab();
      if (pinned) {
        await __RUNCTX__.ResultWatcher.pasteResultIfNeeded({
          getState: getRuntimeState,
          setState: setRuntimeState,
        });
      }
    } catch {
    } finally {
      resultTickRunning = false;
    }
  }, scaledResultInterval());
}

function startIntervals() {
  stopAllIntervals();
  startPayloadInterval();
  startResultInterval();
}

// Modified isPinnedToThisTab to check context
async function isPinnedToThisTab() {
  if (!isContextValidFlag || !isContextValid()) {
    isContextValidFlag = false;
    stopAllIntervals();
    return false;
  }
  try {
    const state = await chrome.storage.local.get(["pinnedTabId"]);
    if (!state.pinnedTabId) return false;
    return ownTabId !== null && state.pinnedTabId === ownTabId;
  } catch (e) {
    if (e.message?.includes("context") || e.message?.includes("Extension context")) {
      handleContextInvalidated();
    } else {
      window.__RUNCTX__?.Logger?.warn?.("isPinnedToThisTab error:", e.message);
    }
    return false;
  }
}

// Start intervals immediately on load to preserve the legacy timing exactly
// (first tick scheduled at T0). The speed factor may still be loading here,
// but normal is 1.0 by default so its timing is identical to legacy.
startIntervals();

// Restart intervals when the speed setting changes so slow/fast take effect
// without a page reload. Normal users never change this, so their intervals
// are created once exactly like legacy.
if (chrome?.storage?.onChanged) {
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (changes.speedMode) {
      startIntervals();
    }
  });
}
