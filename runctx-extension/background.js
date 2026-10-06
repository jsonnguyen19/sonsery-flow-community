// Import the single source of truth for speed factors.
// Background is a service worker (uses self, no window).
importScripts("utils/speed-config.js");

// Bridge proxy to bypass Private Network Access (PNA) restriction
// The bridge may listen on a port other than 8765 if the base port is
// taken/blocked (Windows reserved ranges from Hyper-V/WSL/Docker). This list
// must match BRIDGE_PORT + BRIDGE_PORT_SCAN_RANGE in runctx/constants.py.
const BRIDGE_PORT_BASE = 8765;
const BRIDGE_PORT_SCAN_RANGE = 20;
const BRIDGE_PORT_CANDIDATES = [
  BRIDGE_PORT_BASE,
  ...Array.from({ length: BRIDGE_PORT_SCAN_RANGE }, (_, i) => BRIDGE_PORT_BASE + i + 1),
];

// Current port. Cached after the first resolve. Reset on fetch failure so the
// next call rescans from scratch (the bridge may restart on another port).
let _activeBridgePort = BRIDGE_PORT_BASE;

// The bridge writes the actual port to .state/watchctx.bridge-port, but the
// extension (service worker) cannot read host files. Instead, probe each
// port with a lightweight fetch to find the live one.
let _resolvingPort = null;

async function resolveBridgePort() {
  if (_resolvingPort) return _resolvingPort;

  _resolvingPort = (async () => {
    for (const port of BRIDGE_PORT_CANDIDATES) {
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 400);
        const resp = await fetch(`http://127.0.0.1:${port}/result`, {
          method: "GET",
          signal: ctrl.signal,
          cache: "no-store",
        });
        clearTimeout(t);
        // Any response (even 404) proves an HTTP server is listening.
        if (resp) {
          _activeBridgePort = port;
          return port;
        }
      } catch {
        // nothing on this port -> try the next one
      }
    }
    return _activeBridgePort;
  })();

  try {
    return await _resolvingPort;
  } finally {
    _resolvingPort = null;
  }
}

function bridgeUrl(endpoint) {
  return `http://127.0.0.1:${_activeBridgePort}${endpoint}`;
}

// ============================================================
// SIDE PANEL - Open panel on action icon click
// ============================================================
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error("sidePanel.setPanelBehavior failed:", error));

// ============================================================
// SPEED MULTIPLIER (background / service worker side)
// ============================================================
// ⚠️ SPEED_FACTORS is defined ONLY in utils/speed-config.js and is
// importScripts()'d at the top of this file. Do not hardcode it again.

async function getSpeedScaledMs(baseMs) {
  try {
    const cfg = self.__RUNCTX_SPEED__;
    const data = await chrome.storage.local.get(["speedMode", "envSettings"]);
    const mode = data.speedMode || data.envSettings?.speedMode || cfg.DEFAULT_SPEED_MODE;
    const factor = cfg.getSpeedFactorFromMode(mode);
    return Math.round(baseMs * factor);
  } catch {
    return baseMs;
  }
}

async function proxyBridgeRequest(endpoint, options = {}) {
  const doFetch = async () => {
    const url = bridgeUrl(endpoint);
    return fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  };

  try {
    return await doFetch();
  } catch (err) {
    // Fetch failed (network / connection refused) -> the bridge may have moved
    // ports. Rescan and retry once.
    //
    // Note: resolveBridgePort() UPDATES _activeBridgePort internally, so
    // compare against the OLD port (before resolve) to detect a change.
    const prevPort = _activeBridgePort;
    const port = await resolveBridgePort();
    if (port === prevPort) {
      // No other port found -> rethrow the original error.
      throw err;
    }
    return await doFetch();
  }
}

async function proxyBridgeJson(endpoint, options = {}) {
  try {
    const res = await proxyBridgeRequest(endpoint, options);
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ============================================================
// TAB CLOSE CLEANUP (pinned tab + processed-payload queue)
// ============================================================
// handle the Community-shared cleanup: the persisted processed-payload queue
// and the pinnedTabId marker.

chrome.tabs.onRemoved.addListener(async (tabId) => {
  // Clean up the persisted processed-payload queue for the closed tab.
  // The queue is written by the content script (`processedPayloadKeys_<tabId>`).
  // Remove it here to avoid leaking storage and to prevent collisions when
  // Chrome reuses tabId for a new tab (a stale queue would make the new tab
  // skip a payload by mistake).
  try {
    await chrome.storage.local.remove(`processedPayloadKeys_${tabId}`);
  } catch {
    // storage failure — ignore, not critical.
  }

  // If the closed tab was pinned by the extension (pinnedTabId used for
  // automation targeting) -> clear it so we no longer target a dead tab.
  const state = await chrome.storage.local.get(["pinnedTabId"]);
  if (state.pinnedTabId === tabId) {
    await chrome.storage.local.set({ pinnedTabId: null });
    console.log(`📍 Cleared pinnedTabId ${tabId} (tab closed)`);
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "RUNCTX_GET_TAB_ID") {
    sendResponse({ tabId: sender.tab?.id ?? null });
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_GET_RESULT") {
    proxyBridgeRequest(`/result?t=${Date.now()}`)
      .then(async (res) => {
        if (!res.ok) {
          sendResponse({ error: `HTTP ${res.status}` });
          return;
        }
        const data = await res.json();
        sendResponse({ data });
      })
      .catch((err) => {
        sendResponse({ error: err.message });
      });
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_GET_LOG") {
    const since = Number.isInteger(message.since) ? message.since : 0;
    const limit = Number.isInteger(message.limit) ? message.limit : 200;
    const safeLimit = Math.min(Math.max(limit, 1), 200);
    proxyBridgeRequest(`/log?since=${since}&limit=${safeLimit}&t=${Date.now()}`)
      .then(async (res) => {
        if (!res.ok) {
          sendResponse({ ok: false, status: res.status });
          return;
        }
        const data = await res.json();
        sendResponse({ ok: true, data });
      })
      .catch((err) => {
        sendResponse({ ok: false, error: err.message });
      });
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_GET_STATE") {
    proxyBridgeRequest(`/state?t=${Date.now()}`)
      .then(async (res) => {
        if (!res.ok) {
          sendResponse({ ok: false, status: res.status });
          return;
        }
        const data = await res.json();
        sendResponse({ ok: true, data });
      })
      .catch((err) => {
        sendResponse({ ok: false, error: err.message });
      });
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_CONSUME_RESULT") {
    proxyBridgeRequest("/result/consume", { method: "POST" })
      .then((res) => {
        sendResponse({ ok: res.ok, status: res.status });
      })
      .catch((err) => {
        sendResponse({ error: err.message });
      });
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_SHUTDOWN") {
    proxyBridgeRequest("/shutdown", { method: "POST" })
      .then((res) => {
        sendResponse({ ok: res.ok, status: res.status });
      })
      .catch((err) => {
        sendResponse({ error: err.message });
      });
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_CHAT") {
    // Shared Pro+Community: tag the next history row with this chat id.
    proxyBridgeJson("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: message.chatId || null }),
    }).then(sendResponse);
    return true;
  }

  if (message?.type === "RUNCTX_BRIDGE_RPC") {
    const tool = message.tool;
    const params = message.params || {};
    const reqId = Number.isInteger(message.id) ? message.id : Date.now();

    if (!tool || typeof tool !== "string") {
      sendResponse({ error: "RUNCTX_BRIDGE_RPC requires 'tool'" });
      return true;
    }

    proxyBridgeRequest("/rpc", {
      method: "POST",
      body: JSON.stringify({ id: reqId, tool, params }),
    })
      .then(async (res) => {
        let data = null;
        try {
          data = await res.json();
        } catch {
          data = null;
        }
        sendResponse({ ok: res.ok, status: res.status, data });
      })
      .catch((err) => {
        sendResponse({ error: err.message });
      });
    return true;
  }
});

// ============================================================
// AUTOMATION TOGGLE — shared by hotkey + action handlers
// ============================================================
//
// Single source for toggle logic: set storage.enabled + broadcast
// RUNCTX_SET_STATE to every tab. Both the hotkey (chrome.commands) and the action handlers
async function setAutomation(nextEnabled) {
  await chrome.storage.local.set({ enabled: nextEnabled });
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs) {
    try {
      await chrome.tabs.sendMessage(tab.id, {
        type: "RUNCTX_SET_STATE",
        enabled: nextEnabled,
      });
    } catch {
      // Tab has no content script — skip.
    }
  }
  console.log(`Automation: ${nextEnabled ? "ON" : "OFF"}`);
  return nextEnabled;
}

async function toggleAutomation() {
  const state = await chrome.storage.local.get(["enabled"]);
  const next = !(state.enabled || false);
  return setAutomation(next);
}

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener(async (command) => {
  console.log("Command received:", command);
  if (command === "toggle-automation") {
    await toggleAutomation();
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "RUNCTX_SET_AUTOMATION") {
    const next = Boolean(message.enabled);
    setAutomation(next)
      .then((v) => sendResponse({ ok: true, enabled: v }))
      .catch((e) => sendResponse({ ok: false, error: String(e?.message || e) }));
    return true;
  }
  return false;
});

// ============================================================
// TOKEN TRACKING - Auto track payload/result
// ============================================================

const TOKEN_STORAGE_KEY = "tokenTracking";

function estimateTokens(text) {
  if (!text) return 0;
  const charCount = typeof text === "string" ? text.length : JSON.stringify(text).length;
  return Math.max(1, Math.ceil(charCount / 4));
}

async function getTokenState() {
  const data = await chrome.storage.local.get([TOKEN_STORAGE_KEY]);
  if (!data[TOKEN_STORAGE_KEY]) {
    const defaultState = {
      total: 0,
      session: 0,
      input: 0,
      output: 0,
      operations: [],
      sessionStart: Date.now(),
    };
    await chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: defaultState });
    return defaultState;
  }
  return data[TOKEN_STORAGE_KEY];
}

async function addTokenUsage({ input, output, label, type = "operation" }) {
  const state = await getTokenState();
  const total = (input || 0) + (output || 0);

  state.total += total;
  state.session += total;
  state.input += input || 0;
  state.output += output || 0;

  state.operations.push({
    timestamp: Date.now(),
    label: label || `${type} ${state.operations.length + 1}`,
    type,
    input: input || 0,
    output: output || 0,
    total,
  });

  // Keep last 100 operations
  if (state.operations.length > 100) {
    state.operations = state.operations.slice(-100);
  }

  await chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: state });
  return state;
}

// Listen for payload/result messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "RUNCTX_TRACK_PAYLOAD") {
    const payloadText = message.payload || "";
    const tokens = estimateTokens(payloadText);
    addTokenUsage({
      input: tokens,
      output: 0,
      label: message.label || "Payload sent",
      type: "payload",
    })
      .then(() => {
        sendResponse({ ok: true, tokens });
      })
      .catch(() => {
        sendResponse({ ok: false });
      });
    return true;
  }

  if (message?.type === "RUNCTX_TRACK_RESULT") {
    const resultText = message.result || "";
    const tokens = estimateTokens(resultText);
    addTokenUsage({
      input: 0,
      output: tokens,
      label: message.label || "Result received",
      type: "result",
    })
      .then(() => {
        sendResponse({ ok: true, tokens });
      })
      .catch(() => {
        sendResponse({ ok: false });
      });
    return true;
  }
});
