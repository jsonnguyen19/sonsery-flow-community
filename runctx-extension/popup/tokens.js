// ============================================================
// TOKEN TRACKING
// ============================================================

function estimateTokens(text) {
  if (!text) return 0;
  const charCount = text.length;
  // Rough estimate: ~4 chars per token
  return Math.max(1, Math.ceil(charCount / 4));
}

const TOKEN_STORAGE_KEY = "tokenTracking";

function getDefaultTokenState() {
  return {
    total: 0,
    session: 0,
    input: 0,
    output: 0,
    operations: [],
    sessionStart: Date.now(),
  };
}

async function getTokenState() {
  const data = await chrome.storage.local.get([TOKEN_STORAGE_KEY]);
  if (!data[TOKEN_STORAGE_KEY]) {
    const defaultState = getDefaultTokenState();
    await chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: defaultState });
    return defaultState;
  }
  return data[TOKEN_STORAGE_KEY];
}

// addTokenUsage is now handled by background.js
// Use chrome.runtime.sendMessage for token tracking

async function resetTokenSession() {
  const state = await getTokenState();
  state.session = 0;
  state.input = 0;
  state.output = 0;
  state.operations = [];
  state.sessionStart = Date.now();
  await chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: state });
  return state;
}

async function renderTokenStats() {
  try {
    const state = await getTokenState();

    const sessionEl = document.getElementById("sessionTokens");
    const inputEl = document.getElementById("inputTokens");
    const outputEl = document.getElementById("outputTokens");
    const inputBar = document.getElementById("inputBar");
    const outputBar = document.getElementById("outputBar");
    const opCountEl = document.getElementById("opCount");
    const avgEl = document.getElementById("avgTokens");

    if (sessionEl)
      sessionEl.innerHTML = `${state.session.toLocaleString()} <span class="sub">tokens</span>`;

    const total = state.input + state.output || 1;
    const inputPct = Math.round((state.input / total) * 100);
    const outputPct = Math.round((state.output / total) * 100);

    if (inputEl)
      inputEl.innerHTML = `${state.input.toLocaleString()} <span class="sub">(${inputPct}%)</span>`;
    if (outputEl)
      outputEl.innerHTML = `${state.output.toLocaleString()} <span class="sub">(${outputPct}%)</span>`;
    if (inputBar) {
      inputBar.style.width = `${inputPct}%`;
      inputBar.className = `fill input${inputPct === 0 ? " zero" : ""}`;
    }
    if (outputBar) {
      outputBar.style.width = `${outputPct}%`;
      outputBar.className = `fill output${outputPct === 0 ? " zero" : ""}`;
    }

    const opCount = state.operations.length;
    if (opCountEl) opCountEl.textContent = `${opCount} total operations`;

    if (avgEl) {
      const avg = opCount > 0 ? Math.round(state.session / opCount) : 0;
      avgEl.textContent = `${avg.toLocaleString()} tokens/operation`;
    }
  } catch (e) {
    console.error("renderTokenStats error:", e);
  }
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.estimateTokens = estimateTokens;
window.__RUNCTX_POPUP__.TOKEN_STORAGE_KEY = TOKEN_STORAGE_KEY;
window.__RUNCTX_POPUP__.getDefaultTokenState = getDefaultTokenState;
window.__RUNCTX_POPUP__.getTokenState = getTokenState;
window.__RUNCTX_POPUP__.resetTokenSession = resetTokenSession;
window.__RUNCTX_POPUP__.renderTokenStats = renderTokenStats;
