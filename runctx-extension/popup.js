// ============================================================
// POPUP ENTRY POINT
// ============================================================
//
// All logic has been split into files under popup/:
//   - popup/prompts.js   (auto-generated from prompts/*.txt via sync-prompts.py)
//   - popup/tokens.js    (token tracking)
//   - popup/settings.js  (env settings)
//   - popup/helpers.js   (getActiveTab, toastInTab, runInTab, injectContext, ...)
//   - popup/tabs.js      (setupTabs, render, renderBadge, renderPinBtn, ...)
//   - popup/actions.js   (all action handlers)
//
// This file only does init: setup listeners + intervals + initial render.

// ============================================================
// INIT
// ============================================================

// Setup tabs.
setupTabs();

// Init theme (system/dark/light) — register the OS listener when mode=system
if (window.__RUNCTX_POPUP__?.initTheme) {
  window.__RUNCTX_POPUP__.initTheme();
}

// Setup settings auto-save
setupSettingsAutoSave();
if (window.__RUNCTX_POPUP__?.setupPayloadQueueControls)
  window.__RUNCTX_POPUP__.setupPayloadQueueControls();

// Setup Automation Speed details modal
if (window.__RUNCTX_POPUP__?.setupSpeedDetails) {
  window.__RUNCTX_POPUP__.setupSpeedDetails();
}

// Setup pin button
setupPinButton();

// Setup manual controls (copy/paste/send/clear)
setupManualControls();

// Setup inject button (combined dropdown)
setupInjectButton();

// Setup showToasts toggle
setupShowToastsToggle();

// Setup play-result-sound toggle
setupPlayResultSoundToggle();

// Setup history tab (refresh/clear/settings cap)
if (window.__RUNCTX_POPUP__?.setupHistoryTab) {
  window.__RUNCTX_POPUP__.setupHistoryTab();
}

// Setup reset tokens button
setupResetTokensButton();

// Automation toggle
const automationInput = document.getElementById("automation");
automationInput.addEventListener("change", sendStateToTab);

// Load showToasts state
loadShowToastsState();

// Load play-result-sound state
loadPlayResultSoundState();

// Load settings after DOM is ready
setTimeout(() => {
  loadSettingsToUI();
}, 100);

// Render initial state
render();

// Initial skills render (if the skills tab is default - rare, but safe)

// Refresh stats/history periodically
setInterval(async () => {
  const activeTab = document.querySelector(".tab-btn.active");
  if (activeTab) {
    const tabName = activeTab.dataset.tab;
    if (tabName === "stats") {
      await renderTokenStats();
    }
  }
}, 5000);

// Also refresh when the popup opens
setInterval(render, 1000);
