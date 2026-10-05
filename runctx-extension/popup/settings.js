// ============================================================
// SETTINGS MANAGEMENT
// ============================================================

const SETTINGS_KEY = "envSettings";

const THEME_KEY = "theme";
const THEME_VALUES = ["system", "dark", "light"];
const DEFAULT_THEME = "system";

function normalizeTheme(value) {
  return THEME_VALUES.includes(value) ? value : DEFAULT_THEME;
}

async function getTheme() {
  const data = await chrome.storage.local.get([THEME_KEY]);
  return normalizeTheme(data[THEME_KEY]);
}

async function saveTheme(theme) {
  const normalized = normalizeTheme(theme);
  await chrome.storage.local.set({ [THEME_KEY]: normalized });
  return normalized;
}

const _themeMedia = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;
let _currentTheme = DEFAULT_THEME;

function _resolveEffectiveTheme(theme) {
  if (theme === "system") {
    return _themeMedia && _themeMedia.matches ? "light" : "dark";
  }
  return theme;
}

function _applyEffective() {
  const effective = _resolveEffectiveTheme(_currentTheme);
  document.documentElement.setAttribute("data-theme", effective);
}

function applyTheme(theme) {
  _currentTheme = normalizeTheme(theme);
  _applyEffective();
}

async function initTheme() {
  const theme = await getTheme();
  applyTheme(theme);
  if (_themeMedia) {
    const onChange = () => {
      if (_currentTheme === "system") _applyEffective();
    };
    if (_themeMedia.addEventListener) _themeMedia.addEventListener("change", onChange);
    else if (_themeMedia.addListener) _themeMedia.addListener(onChange);
  }
}

async function getEnvSettings() {
  const data = await chrome.storage.local.get([SETTINGS_KEY]);
  const defaultSettings = {
    shell: "auto",
    techStack: "auto",
    packageManager: "auto",
    autoInject: true,
  };
  if (!data[SETTINGS_KEY]) {
    await chrome.storage.local.set({ [SETTINGS_KEY]: defaultSettings });
    return defaultSettings;
  }
  return { ...defaultSettings, ...data[SETTINGS_KEY] };
}

async function saveEnvSettings(settings) {
  await chrome.storage.local.set({ [SETTINGS_KEY]: settings });
}

// Display maps + max-response constants live in utils/env-config.js
// (single source of truth, shared across popup and content scripts).
const getShellDisplay = (shell) => window.__RUNCTX_ENV__.getShellDisplay(shell);
const getTechDisplay = (tech) => window.__RUNCTX_ENV__.getTechDisplay(tech);
const getPmDisplay = (pm) => window.__RUNCTX_ENV__.getPmDisplay(pm);

function buildEnvironmentContext(settings, hostname) {
  const parts = [];

  // Only add if NOT auto and value exists
  if (settings?.shell && settings.shell !== "auto") {
    const shellName = getShellDisplay(settings.shell);
    if (shellName) parts.push(`shell=${shellName}`);
  }
  if (settings?.techStack && settings.techStack !== "auto") {
    const techName = getTechDisplay(settings.techStack);
    if (techName) parts.push(`stack=${techName}`);
  }
  if (settings?.packageManager && settings.packageManager !== "auto") {
    const pmName = getPmDisplay(settings.packageManager);
    if (pmName) parts.push(`pm=${pmName}`);
  }

  // Add max result lines limit if set (> 0). The sentence is built in
  // utils/env-config.js so popup and content scripts stay identical.
  const maxLines = window.__RUNCTX_ENV__.resolveMaxLines(settings?.maxLines, hostname || "");
  if (maxLines > 0) {
    parts.push(window.__RUNCTX_ENV__.getMaxLinesInstruction(maxLines));
  }

  if (parts.length === 0) return "";
  return `\n\n[ENV: ${parts.join(", ")}]`;
}

async function updateSettingsFromUI() {
  const shellSelect = document.getElementById("shellSelect");
  const techSelect = document.getElementById("techStackSelect");
  const pmSelect = document.getElementById("pmSelect");
  const maxLengthSelect = document.getElementById("maxResponseLength");

  const settings = {
    shell: shellSelect?.value || "auto",
    techStack: techSelect?.value || "auto",
    packageManager: pmSelect?.value || "auto",
    maxLines: maxLengthSelect?.value === "auto" ? "auto" : parseInt(maxLengthSelect?.value) || 0,
  };

  const existing = await getEnvSettings();
  const merged = { ...existing, ...settings };
  await saveEnvSettings(merged);
}

async function loadSettingsToUI() {
  const settings = await getEnvSettings();

  const shellSelect = document.getElementById("shellSelect");
  const techSelect = document.getElementById("techStackSelect");
  const pmSelect = document.getElementById("pmSelect");
  const maxLengthSelect = document.getElementById("maxResponseLength");
  const speedModeSelect = document.getElementById("speedModeSelect");
  const themeSelect = document.getElementById("themeSelect");

  if (themeSelect) {
    themeSelect.value = await getTheme();
  }

  if (shellSelect) {
    shellSelect.value = settings.shell || "auto";
  }
  if (techSelect) {
    techSelect.value = settings.techStack || "auto";
  }
  if (pmSelect) {
    pmSelect.value = settings.packageManager || "auto";
  }
  if (maxLengthSelect) {
    const val = settings.maxLines;
    // Never saved = auto (same rule as resolveMaxLines in env-config.js).
    maxLengthSelect.value = val == null || val === "auto" ? "auto" : String(val);
    // Force refresh select display
    maxLengthSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }

  if (speedModeSelect) {
    const mode = await getSpeedMode();
    speedModeSelect.value = mode;
  }
}

function setupSettingsAutoSave() {
  const shellSelect = document.getElementById("shellSelect");
  const techSelect = document.getElementById("techStackSelect");
  const pmSelect = document.getElementById("pmSelect");
  const maxLengthSelect = document.getElementById("maxResponseLength");
  const speedModeSelect = document.getElementById("speedModeSelect");
  const themeSelect = document.getElementById("themeSelect");

  if (themeSelect) {
    themeSelect.addEventListener("change", async () => {
      const normalized = await saveTheme(themeSelect.value);
      applyTheme(normalized);
    });
  }

  const saveAndUpdate = async () => {
    await updateSettingsFromUI();
  };

  if (shellSelect) {
    shellSelect.addEventListener("change", saveAndUpdate);
  }
  if (techSelect) {
    techSelect.addEventListener("change", saveAndUpdate);
  }
  if (pmSelect) {
    pmSelect.addEventListener("change", saveAndUpdate);
  }
  if (maxLengthSelect) {
    maxLengthSelect.addEventListener("change", saveAndUpdate);
  }
  if (speedModeSelect) {
    speedModeSelect.addEventListener("change", async () => {
      await saveSpeedMode(speedModeSelect.value);
    });
  }
}

// ============================================================
// AUTOMATION SPEED — DETAILS MODAL
// ============================================================

const SPEED_MODE_META = {
  slow: { label: "Slow", note: "Slower cadence — safest pacing" },
  normal: { label: "Normal", note: "Default baseline" },
  fast: { label: "Fast", note: "Faster than baseline" },
  veryFast: { label: "Very Fast", note: "Bypass — no delay" },
};

const SPEED_BASE_DELAY_MS =
  (typeof window !== "undefined" && window.__RUNCTX_SPEED__?.RESULT_TO_SEND_BASE_MS) || 800;

function formatMs(ms) {
  return `${ms}ms`;
}

async function renderSpeedDetails() {
  const tbody = document.getElementById("speedDetailsBody");
  if (!tbody) return;

  const factors = (window.__RUNCTX_POPUP__ && window.__RUNCTX_POPUP__.SPEED_FACTORS) || {};
  const currentMode = await getSpeedMode();

  const order = ["slow", "normal", "fast", "veryFast"];
  tbody.innerHTML = "";

  order.forEach((mode) => {
    const factor = factors[mode];
    const meta = SPEED_MODE_META[mode] || { label: mode, note: "" };
    const isBypass = factor === 0;
    const delay = isBypass ? 0 : Math.round(SPEED_BASE_DELAY_MS * factor);

    const tr = document.createElement("tr");
    if (mode === currentMode) tr.classList.add("is-active");

    const noteText = isBypass ? `${meta.note} (delay = 0)` : `${meta.note} ×${factor}`;

    tr.innerHTML = `
      <td class="speed-mode-name">${meta.label}${mode === currentMode ? " •" : ""}</td>
      <td class="speed-col-mono">${factor}</td>
      <td class="speed-col-mono">${formatMs(delay)}</td>
      <td>${noteText}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function openSpeedDetailsModal() {
  const modal = document.getElementById("speedDetailsModal");
  if (!modal) return;
  await renderSpeedDetails();
  modal.hidden = false;
}

function closeSpeedDetailsModal() {
  const modal = document.getElementById("speedDetailsModal");
  if (modal) modal.hidden = true;
}

function setupSpeedDetails() {
  const btn = document.getElementById("speedDetailsBtn");
  const modal = document.getElementById("speedDetailsModal");
  const closeBtn = document.getElementById("speedDetailsClose");
  if (!btn || !modal) return;

  btn.addEventListener("click", openSpeedDetailsModal);
  if (closeBtn) closeBtn.addEventListener("click", closeSpeedDetailsModal);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeSpeedDetailsModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.hidden) closeSpeedDetailsModal();
  });
}

// ============================================================
// PAYLOAD ID QUEUE — View & Reset
// ============================================================

async function getTrackedPayloadIds() {
  const tabs = await chrome.tabs.query({});
  const keys = tabs.map((t) => `processedPayloadKeys_${t.id}`);
  if (!keys.length) return [];
  const data = await chrome.storage.local.get(keys);
  const all = [];
  for (const k of keys) {
    if (Array.isArray(data[k])) all.push(...data[k]);
  }
  // dedup
  return [...new Set(all)];
}

async function resetTrackedPayloadIds() {
  const tabs = await chrome.tabs.query({});
  const keys = tabs.map((t) => `processedPayloadKeys_${t.id}`);
  if (keys.length) await chrome.storage.local.remove(keys);
}

function renderPayloadIdsList(ids, listEl) {
  if (!ids.length) {
    listEl.innerHTML =
      '<span style="color:var(--text-muted);font-size:11px">Queue is empty.</span>';
    return;
  }
  listEl.innerHTML =
    '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">' +
    ids.length +
    " / 100 entries tracked (oldest → newest):</div>" +
    '<pre style="font-size:10px;line-height:1.5;max-height:160px;overflow-y:auto;' +
    'background:var(--bg-secondary,#1e1e1e);padding:6px 8px;border-radius:4px;margin:0">' +
    ids
      .map((id, i) => {
        const isIdKey = id.startsWith("id:");
        const val = id.replace(/^(id:|h:)/, "");
        const prefix = isIdKey
          ? '<span style="color:#7ec8a0">id</span>'
          : '<span style="color:#888"> h</span>';
        const num = String(i + 1).padStart(3, " ");
        return '<span style="color:var(--text-muted)">' + num + ".</span> " + prefix + ":" + val;
      })
      .join("\n") +
    "</pre>";
}

// Chuan hoa input search thanh key dang "id:<n>" hoac "h:<hash>".
// Ho tro: "123", "id:123", "h:abc", "abc" (-> h:abc).
function normalizeSearchQuery(raw) {
  const q = String(raw || "").trim();
  if (!q) return { key: "", kind: "empty" };
  const lower = q.toLowerCase();
  if (lower.startsWith("id:")) return { key: "id:" + q.slice(3).trim(), kind: "id" };
  if (lower.startsWith("h:")) return { key: "h:" + q.slice(2).trim(), kind: "hash" };
  if (/^\d+$/.test(q)) return { key: "id:" + q, kind: "id" };
  return { key: "h:" + q, kind: "hash" };
}

function setupPayloadQueueControls() {
  const viewBtn = document.getElementById("viewPayloadIdsBtn");
  const resetBtn = document.getElementById("resetPayloadQueueBtn");
  const listEl = document.getElementById("payloadIdsList");
  const searchInput = document.getElementById("payloadIdSearchInput");
  const searchBtn = document.getElementById("searchPayloadIdBtn");
  if (!viewBtn || !resetBtn || !listEl) return;

  let isOpen = false;

  viewBtn.addEventListener("click", async () => {
    if (isOpen) {
      listEl.style.display = "none";
      viewBtn.textContent = "View";
      isOpen = false;
      return;
    }
    const ids = await getTrackedPayloadIds();
    renderPayloadIdsList(ids, listEl);
    listEl.style.display = "block";
    viewBtn.textContent = "Hide";
    isOpen = true;
  });

  resetBtn.addEventListener("click", async () => {
    if (!confirm("Reset all tracked payload IDs? Previously seen payloads may be re-executed."))
      return;
    await resetTrackedPayloadIds();
    listEl.innerHTML = '<span style="color:#7ec8a0;font-size:11px">✓ Queue cleared.</span>';
    listEl.style.display = "block";
    viewBtn.textContent = "View";
    isOpen = false;
  });

  async function runSearch() {
    if (!searchInput) return;
    const { key, kind } = normalizeSearchQuery(searchInput.value);
    if (kind === "empty") {
      // O trong -> hien lai danh sach binh thuong nhu View IDs.
      const ids = await getTrackedPayloadIds();
      renderPayloadIdsList(ids, listEl);
      listEl.style.display = "block";
      isOpen = true;
      viewBtn.textContent = "Hide";
      return;
    }

    const ids = await getTrackedPayloadIds();
    const exactIdx = ids.indexOf(key);
    const found = exactIdx !== -1;

    // Search ra dung 1 dong: key vua nhap + trang thai found/not found.
    // Khong hien related matches / banner roi.
    const val = key.replace(/^(id:|h:)/, "");
    const prefix = key.startsWith("id:")
      ? '<span style="color:#7ec8a0">id</span>'
      : '<span style="color:#888"> h</span>';
    const status = found
      ? '<span style="color:#7ec8a0;margin-left:8px">✓ found #' +
        (exactIdx + 1) +
        " / " +
        ids.length +
        "</span>"
      : '<span style="color:#e06c6c;margin-left:8px">✗ not found</span>';

    listEl.innerHTML =
      '<pre style="font-size:10px;line-height:1.5;background:var(--bg-secondary,#1e1e1e);' +
      'padding:6px 8px;border-radius:4px;margin:0;white-space:pre-wrap;word-break:break-all">' +
      prefix +
      ":" +
      val +
      status +
      "</pre>";
    listEl.style.display = "block";
    viewBtn.textContent = "Hide";
    isOpen = true;
  }

  if (searchBtn) searchBtn.addEventListener("click", runSearch);
  if (searchInput) {
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runSearch();
      }
    });
  }
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.SETTINGS_KEY = SETTINGS_KEY;
window.__RUNCTX_POPUP__.THEME_KEY = THEME_KEY;
window.__RUNCTX_POPUP__.THEME_VALUES = THEME_VALUES;
window.__RUNCTX_POPUP__.DEFAULT_THEME = DEFAULT_THEME;
window.__RUNCTX_POPUP__.normalizeTheme = normalizeTheme;
window.__RUNCTX_POPUP__.getTheme = getTheme;
window.__RUNCTX_POPUP__.saveTheme = saveTheme;
window.__RUNCTX_POPUP__.applyTheme = applyTheme;
window.__RUNCTX_POPUP__.initTheme = initTheme;
window.__RUNCTX_POPUP__.getEnvSettings = getEnvSettings;
window.__RUNCTX_POPUP__.saveEnvSettings = saveEnvSettings;
window.__RUNCTX_POPUP__.getShellDisplay = getShellDisplay;
window.__RUNCTX_POPUP__.getTechDisplay = getTechDisplay;
window.__RUNCTX_POPUP__.getPmDisplay = getPmDisplay;
window.__RUNCTX_POPUP__.buildEnvironmentContext = buildEnvironmentContext;
window.__RUNCTX_POPUP__.updateSettingsFromUI = updateSettingsFromUI;
window.__RUNCTX_POPUP__.loadSettingsToUI = loadSettingsToUI;
window.__RUNCTX_POPUP__.setupSettingsAutoSave = setupSettingsAutoSave;
window.__RUNCTX_POPUP__.setupSpeedDetails = setupSpeedDetails;
window.__RUNCTX_POPUP__.openSpeedDetailsModal = openSpeedDetailsModal;
window.__RUNCTX_POPUP__.closeSpeedDetailsModal = closeSpeedDetailsModal;
window.__RUNCTX_POPUP__.setupPayloadQueueControls = setupPayloadQueueControls;
window.__RUNCTX_POPUP__.getTrackedPayloadIds = getTrackedPayloadIds;
window.__RUNCTX_POPUP__.resetTrackedPayloadIds = resetTrackedPayloadIds;
