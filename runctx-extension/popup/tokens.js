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

// Reset the CURRENT SESSION counters only (session/input/output/operations).
// Cumulative `total` is preserved so long-term history isn't lost.
async function resetSession() {
  if (
    !confirm(
      "Reset the current session? This clears session tokens, input/output split, and the operations list. Cumulative totals are kept."
    )
  )
    return;
  // Delegate to background (single writer of `tokenTracking`) to avoid the
  // read-modify-write race with addTokenUsage (background.js). The popup
  // must NOT write storage directly here, otherwise a concurrent track event
  // could be clobbered (lost-update on `total`).
  await new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage({ type: "RUNCTX_RESET_SESSION" }, () => {
        const err = chrome.runtime.lastError;
        if (err) {
          // Background not updated (e.g. extension not reloaded). Surface it
          // so the user/dev knows the reset was a no-op rather than silent.
          console.warn("RUNCTX_RESET_SESSION failed:", err.message || err);
        }
        resolve();
      });
    } catch (e) {
      console.warn("RUNCTX_RESET_SESSION error:", e);
      resolve();
    }
  });
  await renderTokenStats();
}

// Re-render the token panel whenever the background updates `tokenTracking`.
// This keeps the UI in sync after a reset (or after any new payload/result
// arrives) without waiting for the next 5s polling tick.
if (typeof chrome !== "undefined" && chrome.storage?.onChanged) {
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (!changes || !changes[TOKEN_STORAGE_KEY]) return;
    // Ignore until the token panel exists in the DOM.
    if (!document.getElementById("sessionTokens")) return;
    renderTokenStats();
  });
}

// Wire the "Reset session" button. This lives in tokens.js (not stats.js)
// because stats.js is Pro-only and is stripped from the Community build,
// while the button itself ships in both editions. Binding here keeps the
// feature self-contained: token panel + reset button + storage listener
// all live in one module that every edition ships.
(function bindResetSessionButton() {
  const btn = document.getElementById("statsResetSession");
  if (!btn) return;
  btn.addEventListener("click", () => resetSession());
})();

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.estimateTokens = estimateTokens;
window.__RUNCTX_POPUP__.TOKEN_STORAGE_KEY = TOKEN_STORAGE_KEY;
window.__RUNCTX_POPUP__.getDefaultTokenState = getDefaultTokenState;
window.__RUNCTX_POPUP__.getTokenState = getTokenState;
window.__RUNCTX_POPUP__.renderTokenStats = renderTokenStats;
window.__RUNCTX_POPUP__.resetSession = resetSession;
