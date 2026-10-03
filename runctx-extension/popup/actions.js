// ============================================================
// ACTION HANDLERS: automation state, pin, reset tokens
// ============================================================
//
// Manual controls (copy/paste/send/clear) -> actions-manual.js
// Inject context + toasts toggle -> actions-inject.js

async function sendStateToTab() {
  const automationInput = document.getElementById("automation");
  const tab = await getActiveTab();
  const enabled = automationInput.checked;
  await chrome.storage.local.set({ enabled });

  try {
    await chrome.tabs.sendMessage(tab.id, {
      type: "RUNCTX_SET_STATE",
      enabled,
    });
  } catch {
    // Tab chua co content script — bo qua. Header #statusEl do
    // renderWatchStatus quan ly.
  }

  renderBadge();
}

// ============================================================
// WATCHCTX STATUS (header #statusEl)
// ============================================================
// Hien thi "watchctx @ <pwd>" khi bridge song, hoac "chua co watchctx".
// Poll moi lan render() duoc goi (setInterval 1s trong popup.js).
//
async function fetchWatchState() {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage({ type: "RUNCTX_BRIDGE_GET_STATE" }, (res) => {
        if (chrome.runtime.lastError || !res?.ok) {
          resolve(null);
          return;
        }
        resolve(res.data?.data || null);
      });
    } catch {
      resolve(null);
    }
  });
}

async function renderWatchStatus() {
  const statusEl = document.getElementById("statusEl");
  if (!statusEl) return;

  const state = await fetchWatchState();
  if (!state) {
    statusEl.textContent = "no watchctx";
    statusEl.classList.add("warn");
    return;
  }

  statusEl.classList.remove("warn");
  const effective = state.active_root || state.pwd;
  statusEl.textContent = effective ? "watchctx @ " + effective : "watchctx @ (unknown pwd)";
}

function setupPinButton() {
  const pinTabBtn = document.getElementById("pinTabBtn");
  pinTabBtn.addEventListener("click", async () => {
    const tab = await getActiveTab();
    if (!tab?.id) return;
    const state = await chrome.storage.local.get(["pinnedTabId"]);
    const pinnedTabId = state.pinnedTabId || null;
    if (pinnedTabId === tab.id) {
      // Unpin
      await chrome.storage.local.set({ pinnedTabId: null });
      toastInTab("Tab unpinned. All tabs will run automation.", "info");
    } else {
      // Pin to this tab
      await chrome.storage.local.set({ pinnedTabId: tab.id });
      toastInTab("Pinned to this tab!", "success");
    }
    renderPinBtn();
  });
}

function setupResetTokensButton() {
  const resetTokensBtn = document.getElementById("resetTokensBtn");
  if (resetTokensBtn) {
    resetTokensBtn.addEventListener("click", async () => {
      if (confirm("Reset session token count?")) {
        await resetTokenSession();
        await renderTokenStats();
      }
    });
  }
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.sendStateToTab = sendStateToTab;
window.__RUNCTX_POPUP__.setupPinButton = setupPinButton;
window.__RUNCTX_POPUP__.setupResetTokensButton = setupResetTokensButton;
window.__RUNCTX_POPUP__.renderWatchStatus = renderWatchStatus;
