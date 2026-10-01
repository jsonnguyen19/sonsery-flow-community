// ============================================================
// TABS + RENDER
// ============================================================

let _tabsOverflowSetup = false;

// Maximum number of tabs shown directly in the bar. Any tab beyond this
// limit is routed through the ⋯ overflow menu. The active tab is always
// kept visible on the bar (swapped with the last visible slot if needed).
const MAX_VISIBLE_TABS = 4;

// Compute overflow state from the DOM. Only the first MAX_VISIBLE_TABS tabs
// stay on the bar; the rest (excluding the active one, which is always
// promoted to the bar) are moved into the ⋯ menu. No static marker needed.
function _setupTabsOverflow() {
  if (_tabsOverflowSetup) return;
  const overflow = document.getElementById("tabsOverflow");
  const overflowBtn = document.getElementById("tabsOverflowBtn");
  const menu = document.getElementById("tabsOverflowMenu");
  const bar = overflow?.closest(".tabs");
  if (!overflow || !overflowBtn || !menu || !bar) return;
  _tabsOverflowSetup = true;

  const closeMenu = () => {
    menu.hidden = true;
    overflowBtn.setAttribute("aria-expanded", "false");
  };

  // All real tab buttons in DOM order (excludes the ⋯ button and menu items).
  const getAllTabs = () => Array.from(bar.querySelectorAll(":scope > .tab-btn[data-tab]"));

  // Tabs whose data-overflow flag is currently set by our own logic.
  const getHiddenTabs = () => getAllTabs().filter((b) => b.dataset.overflow === "true");

  // Recompute which tabs belong on the bar vs. in the ⋯ menu.
  // Rule: if total <= MAX_VISIBLE_TABS -> show all, no ⋯ button.
  //       otherwise keep the first MAX_VISIBLE_TABS, promote the active
  //       tab into the bar (swapping with the last visible one if needed),
  //       and flag every remaining tab as overflow.
  const applyOverflowFlags = () => {
    const tabs = getAllTabs();
    const total = tabs.length;
    const needsOverflow = total > MAX_VISIBLE_TABS;

    if (!needsOverflow) {
      tabs.forEach((t) => {
        delete t.dataset.overflow;
      });
      return;
    }

    const active = tabs.find((t) => t.classList.contains("active"));
    const visible = new Set(tabs.slice(0, MAX_VISIBLE_TABS));

    // Always keep the active tab visible: if it would be pushed into the
    // menu, swap it with the last visible tab.
    if (active && !visible.has(active)) {
      const lastVisible = tabs[MAX_VISIBLE_TABS - 1];
      visible.delete(lastVisible);
      visible.add(active);
    }

    tabs.forEach((t) => {
      if (visible.has(t)) {
        delete t.dataset.overflow;
      } else {
        t.dataset.overflow = "true";
      }
    });
  };

  const updateCollapsed = () => {
    applyOverflowFlags();
    const hasOverflow = getHiddenTabs().length > 0;
    bar.classList.toggle("tabs--collapsed", hasOverflow);
    if (!hasOverflow) {
      closeMenu();
    } else if (!menu.hidden) {
      // Keep an open menu anchored to the ⋯ button across resizes.
      positionMenu();
    }
  };

  // Reflect whether one of the hidden tabs is currently active by tinting the
  // ⋯ button. Without this, an active tab inside the menu is invisible to the
  // user whenever the menu is closed.
  const syncOverflowIndicator = () => {
    const hasActiveHidden = getHiddenTabs().some((src) => src.classList.contains("active"));
    overflowBtn.classList.toggle("has-active", hasActiveHidden);
  };

  const renderMenu = () => {
    menu.innerHTML = "";
    getHiddenTabs().forEach((src) => {
      const item = document.createElement("button");
      item.className = "tab-btn";
      item.dataset.tab = src.dataset.tab;
      // Icon-only tabs have no textContent; fall back to aria-label/title so
      // the overflow menu still shows a readable label next to the icon.
      const label =
        src.getAttribute("aria-label") || src.getAttribute("title") || src.textContent.trim();
      // Clone the source icon (if any) so the menu item matches the bar tab.
      const icon = src.querySelector("svg.tab-icon");
      if (icon) {
        const iconClone = icon.cloneNode(true);
        iconClone.classList.remove("tab-icon");
        iconClone.classList.add("tab-icon-menu");
        item.appendChild(iconClone);
      }
      const labelEl = document.createElement("span");
      labelEl.className = "tab-label";
      labelEl.textContent = label;
      item.appendChild(labelEl);
      if (src.classList.contains("active")) item.classList.add("active");
      item.addEventListener("click", () => {
        src.click();
        closeMenu();
        // Re-render so the menu reflects the new active tab (the source button
        // is hidden from the bar, so it can't show feedback itself).
        renderMenu();
      });
      menu.appendChild(item);
    });
    syncOverflowIndicator();
  };

  // Menu is position:fixed to escape the card's overflow clipping; place it
  // just below the ⋯ button, right-aligned.
  const positionMenu = () => {
    const r = overflowBtn.getBoundingClientRect();
    menu.style.top = `${r.bottom + 4}px`;
    menu.style.right = `${window.innerWidth - r.right}px`;
  };

  overflowBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const willOpen = menu.hidden;
    if (willOpen) {
      renderMenu();
      menu.hidden = false;
      positionMenu();
      overflowBtn.setAttribute("aria-expanded", "true");
    } else {
      closeMenu();
    }
  });

  document.addEventListener("click", (e) => {
    if (!overflow.contains(e.target)) closeMenu();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });

  // React to any active-tab change: re-evaluate which tab must stay on the
  // bar (the active one is always promoted) and refresh the ⋯ indicator.
  const activeObserver = new MutationObserver(() => {
    updateCollapsed();
    syncOverflowIndicator();
  });
  getAllTabs().forEach((src) => {
    activeObserver.observe(src, { attributes: true, attributeFilter: ["class"] });
  });

  // Initial layout + keep the menu anchored while open on resize.
  updateCollapsed();
  syncOverflowIndicator();
  window.addEventListener("resize", () => {
    updateCollapsed();
    if (!menu.hidden) positionMenu();
  });
}

function setupTabs() {
  _setupTabsOverflow();

  // Only real tab buttons (with data-tab); excludes the ⋯ overflow button.
  const tabBtns = document.querySelectorAll(".tab-btn[data-tab]");
  const tabContents = {
    flow: document.getElementById("tab-flow"),
    stats: document.getElementById("tab-stats"),
    history: document.getElementById("tab-history"),
    settings: document.getElementById("tab-settings"),
  };

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", async () => {
      // Update active tab button
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      // Update content
      const tabName = btn.dataset.tab;
      Object.entries(tabContents).forEach(([name, el]) => {
        if (el) {
          el.classList.toggle("active", name === tabName);
        }
      });

      // Refresh data when switching to stats/history
      if (tabName === "stats") {
        await renderTokenStats();
      }

      // Load history when switching to history tab
      if (tabName === "history") {
        window.__RUNCTX_POPUP__?.loadHistory?.();
      }
    });
  });
}

async function renderPinBtn() {
  const tab = await getActiveTab();
  const state = await chrome.storage.local.get(["pinnedTabId"]);
  const pinnedTabId = state.pinnedTabId || null;
  const isPinned = pinnedTabId === tab?.id;
  const pinTabBtn = document.getElementById("pinTabBtn");
  const label = isPinned ? "Unpin this tab" : "Pin this tab";
  // Preserve the icon node; only update the text label + a11y strings.
  const labelEl = pinTabBtn.querySelector(".pin-tab-label");
  if (labelEl) {
    labelEl.textContent = label;
  } else {
    // Fallback if markup is ever changed to a plain text button.
    pinTabBtn.textContent = label;
  }
  pinTabBtn.title = label;
  pinTabBtn.setAttribute("aria-label", label);
  pinTabBtn.classList.toggle("pinned", isPinned);
  pinTabBtn.style.background = "";
  pinTabBtn.style.borderColor = "";
  pinTabBtn.style.color = "";
}

function updateManualControls() {
  const manualControls = document.getElementById("manualControls");
  // Quick Actions are always shown, even when automation is ON
  manualControls.style.display = "block";
}

function renderBadge() {
  const automationInput = document.getElementById("automation");
  const badgeEl = document.getElementById("badge");
  const isOn = automationInput.checked;
  badgeEl.textContent = isOn ? "ON" : "OFF";
  badgeEl.className = isOn ? "badge on" : "badge off";
  badgeEl.style.background = "";
  badgeEl.style.color = "";
  // Keep manual controls visibility in sync with badge state
  updateManualControls();
}

async function render() {
  const state = await chrome.storage.local.get([
    "enabled",
    "payloadCount",
    "resultCount",
    "lastPayloadAt",
    "lastResultAt",
    "pinnedTabId",
  ]);

  const automationInput = document.getElementById("automation");
  automationInput.checked = Boolean(state.enabled);

  renderBadge();
  renderPinBtn();
  if (typeof window.__RUNCTX_POPUP__?.renderWatchStatus === "function") {
    window.__RUNCTX_POPUP__.renderWatchStatus();
  }

  // NOTE: loadSettingsToUI() is already called once when the popup opens
  // (popup.js). Do NOT call it again here: render() runs every second via
  // setInterval and would re-issue RPCs / overwrite the UI while the user
  // is interacting.

  // Render token stats if stats tab is active
  const activeTab = document.querySelector(".tab-btn.active");
  if (activeTab) {
    const tabName = activeTab.dataset.tab;
    if (tabName === "stats") {
      await renderTokenStats();
    }
  }
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.setupTabs = setupTabs;
window.__RUNCTX_POPUP__.renderPinBtn = renderPinBtn;
window.__RUNCTX_POPUP__.updateManualControls = updateManualControls;
window.__RUNCTX_POPUP__.renderBadge = renderBadge;
window.__RUNCTX_POPUP__.render = render;
