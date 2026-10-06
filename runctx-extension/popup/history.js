// ============================================================
// PAYLOAD HISTORY TAB
// ============================================================
// Read .state/payload_history.json via RPC (get_history / get_history_detail
// / clear_history / set_history_cap). Renders the list rows + detail drawer.
//
// Uses window.__RUNCTX__.RpcClient (from services/rpc-client.js).
// Style class prefix: .hist-*.

(function () {
  "use strict";

  const CAP_DEFAULT = 100;
  const CAP_MIN = 20;
  const CAP_MAX = 1000;
  const LIST_LIMIT = 200;

  let _listCache = [];
  let _expandedKey = null; // `${id}:${ts}` of the row with an open detail
  let _loading = false;
  // Active chat_id filter. Empty string = show all rows. Read from the
  // #histChatFilter input; applied server-side via RpcClient.getHistory.
  let _chatFilter = "";

  function _keyOf(row) {
    return `${row.id}:${row.ts}`;
  }

  function _fmtTime(ms) {
    try {
      const d = new Date(ms);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      const ss = String(d.getSeconds()).padStart(2, "0");
      return `${hh}:${mm}:${ss}`;
    } catch {
      return "--:--:--";
    }
  }

  function _shortTool(tool) {
    if (!tool) return "?";
    return String(tool).slice(0, 24);
  }

  function _getRpc() {
    return window.__RUNCTX__?.RpcClient;
  }

  function _rowEl(row) {
    const wrap = document.createElement("div");
    wrap.className = "hist-row";
    wrap.dataset.key = _keyOf(row);
    if (row.status === "error") wrap.classList.add("is-error");
    else wrap.classList.add("is-ok");

    const head = document.createElement("button");
    head.type = "button";
    head.className = "hist-row-head";

    const dot = document.createElement("span");
    dot.className = "hist-dot";

    const tool = document.createElement("span");
    tool.className = "hist-tool";
    tool.textContent = _shortTool(row.tool);
    tool.title = row.tool || "";

    const time = document.createElement("span");
    time.className = "hist-time";
    time.textContent = _fmtTime(row.ts);

    const duration = document.createElement("span");
    duration.className = "hist-duration";
    duration.textContent = `${row.duration_ms}ms`;

    const summary = document.createElement("span");
    summary.className = "hist-summary";
    // Prefix the chat id (short) so a filtered list is easy to scan, but keep
    // the payload summary as the dominant text.
    if (row.chat_id) {
      const cid = document.createElement("span");
      cid.className = "hist-chat-pill";
      cid.textContent = _shortChat(row.chat_id);
      cid.title = `Chat: ${row.chat_id}`;
      summary.appendChild(cid);
      summary.appendChild(document.createTextNode(" "));
    }
    const sumText = document.createElement("span");
    sumText.textContent = row.summary || "";
    summary.appendChild(sumText);
    if (row.summary) summary.title = row.summary;

    head.appendChild(dot);
    head.appendChild(tool);
    head.appendChild(time);
    head.appendChild(duration);
    head.appendChild(summary);

    wrap.appendChild(head);

    head.addEventListener("click", () => _toggleDetail(wrap, row));
    return wrap;
  }

  // Compact chat id for the row: keep the tail (session ids are often UUIDs;
  // the distinguishing part is usually at the end).
  function _shortChat(id) {
    const s = String(id || "");
    if (s.length <= 10) return s;
    return `…${s.slice(-8)}`;
  }

  async function _toggleDetail(wrap, row) {
    const key = _keyOf(row);
    const existing = wrap.querySelector(".hist-detail");
    if (existing) {
      existing.remove();
      wrap.classList.remove("is-expanded");
      if (_expandedKey === key) _expandedKey = null;
      return;
    }

    // Only one detail open at a time — close the previous one.
    document.querySelectorAll(".hist-detail").forEach((el) => el.remove());
    document
      .querySelectorAll(".hist-row.is-expanded")
      .forEach((el) => el.classList.remove("is-expanded"));
    wrap.classList.add("is-expanded");
    _expandedKey = key;

    const detail = document.createElement("div");
    detail.className = "hist-detail";
    detail.innerHTML = '<div class="hist-detail-loading">Loading…</div>';
    wrap.appendChild(detail);

    const Rpc = _getRpc();
    if (!Rpc) {
      detail.innerHTML = '<div class="hist-detail-error">RPC not available</div>';
      return;
    }

    const res = await Rpc.getHistoryDetail(row.id, row.ts);
    if (!res || !res.ok) {
      const err = res?.data?.error || res?.error || "Failed to load detail";
      detail.innerHTML = `<div class="hist-detail-error">${_escape(err)}</div>`;
      return;
    }

    const payload = res.data?.data?.[0]?.row;
    if (!payload) {
      detail.innerHTML = '<div class="hist-detail-error">Not found</div>';
      return;
    }

    detail.innerHTML = "";
    // Detail returns FULL payload/result (unlike the list's 'summary' preview).
    detail.appendChild(_section("Payload", payload.payload || payload.summary || ""));
    detail.appendChild(_section("Result", payload.result || ""));
  }

  function _section(title, body) {
    const box = document.createElement("div");
    box.className = "hist-detail-section";
    const h = document.createElement("div");
    h.className = "hist-detail-title";
    h.textContent = title;
    const pre = document.createElement("pre");
    pre.className = "hist-detail-body";
    pre.textContent = body;
    box.appendChild(h);
    box.appendChild(pre);
    return box;
  }

  function _escape(s) {
    return String(s).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
    );
  }

  function _renderList(rows) {
    const listEl = document.getElementById("histList");
    const emptyEl = document.getElementById("histEmpty");
    if (!listEl || !emptyEl) return;
    listEl.innerHTML = "";

    if (!rows || rows.length === 0) {
      emptyEl.style.display = "flex";
      return;
    }
    emptyEl.style.display = "none";

    const frag = document.createDocumentFragment();
    rows.forEach((row) => frag.appendChild(_rowEl(row)));
    listEl.appendChild(frag);
  }

  function _updateHeader(total, cap, filtered) {
    const countEl = document.getElementById("histCount");
    const capEl = document.getElementById("histCapLabel");
    if (countEl) countEl.textContent = String(total ?? 0);
    if (capEl) {
      const base = `cap ${cap ?? CAP_DEFAULT}`;
      capEl.textContent = filtered ? `${base} · filtered` : base;
    }
  }

  async function loadHistory() {
    if (_loading) return;
    _loading = true;
    try {
      const Rpc = _getRpc();
      if (!Rpc) {
        _renderList([]);
        _updateHeader(0, CAP_DEFAULT, false);
        return;
      }
      const res = await Rpc.getHistory(LIST_LIMIT, 0, _chatFilter || null);
      if (!res || !res.ok) {
        _renderList([]);
        _updateHeader(0, CAP_DEFAULT, false);
        return;
      }
      const payload = res.data?.data?.[0];
      const rows = Array.isArray(payload?.rows) ? payload.rows : [];
      _listCache = rows;
      _renderList(rows);
      _updateHeader(payload?.total ?? rows.length, payload?.cap ?? CAP_DEFAULT, !!payload?.chat_id);
    } finally {
      _loading = false;
    }
  }

  async function _clearAll() {
    const Rpc = _getRpc();
    if (!Rpc) return;
    const ok = window.confirm("Clear the entire payload history?");
    if (!ok) return;
    const res = await Rpc.clearHistory();
    if (!res || !res.ok) {
      console.warn("[history] clear failed:", res?.error);
      return;
    }
    _listCache = [];
    _renderList([]);
    _updateHeader(0, _readCurrentCap());
  }

  // ============ SETTINGS: CAP INPUT ============

  function _readCurrentCap() {
    const el = document.getElementById("histCapLabel");
    const m = el?.textContent?.match(/cap\s+(\d+)/);
    return m ? parseInt(m[1], 10) : CAP_DEFAULT;
  }

  async function _loadCapToSettings() {
    const select = document.getElementById("historyCapSelect");
    if (!select) return;
    // Read the current cap from the backend via get_history (no separate tool needed).
    const Rpc = _getRpc();
    if (!Rpc) return;
    const res = await Rpc.getHistory(1, 0);
    const cap = res?.data?.data?.[0]?.cap;
    if (typeof cap !== "number") return;
    // If the current cap is not in the options list, add a temporary option.
    const val = String(cap);
    if (!Array.from(select.options).some((o) => o.value === val)) {
      const opt = document.createElement("option");
      opt.value = val;
      opt.textContent = val;
      select.appendChild(opt);
    }
    select.value = val;
  }

  function _clampCap(raw) {
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n)) return CAP_DEFAULT;
    return Math.max(CAP_MIN, Math.min(CAP_MAX, n));
  }

  function setupHistorySettings() {
    const select = document.getElementById("historyCapSelect");
    if (!select) return;

    select.addEventListener("change", async () => {
      const cap = _clampCap(select.value);
      select.value = String(cap);
      const Rpc = _getRpc();
      if (!Rpc) return;
      const res = await Rpc.setHistoryCap(cap);
      if (!res || !res.ok) {
        console.warn("[history] set cap failed:", res?.error);
        return;
      }
      _updateHeader(undefined, cap);
      // If the History tab is open, reload the list to reflect the change.
      const histTab = document.getElementById("tab-history");
      if (histTab?.classList.contains("active")) loadHistory();
    });
  }

  // ============ WIRE BUTTONS ============

  function setupHistoryTab() {
    const refreshBtn = document.getElementById("histRefreshBtn");
    const clearBtn = document.getElementById("histClearBtn");
    if (refreshBtn) refreshBtn.addEventListener("click", loadHistory);
    if (clearBtn) clearBtn.addEventListener("click", _clearAll);

    // Chat filter: type an id -> filter rows server-side. Enter applies
    // immediately; clearing the input resets to the full list.
    const chatInput = document.getElementById("histChatFilter");
    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          _applyChatFilter(chatInput.value);
        } else if (e.key === "Escape") {
          e.preventDefault();
          chatInput.value = "";
          _applyChatFilter("");
        }
      });
      chatInput.addEventListener("input", () => {
        // Live reset when the input becomes empty; otherwise wait for Enter so
        // we do not spam the bridge on every keystroke.
        if (!chatInput.value.trim() && _chatFilter) _applyChatFilter("");
      });
    }

    const chatClearBtn = document.getElementById("histChatClearBtn");
    if (chatClearBtn) {
      chatClearBtn.addEventListener("click", () => {
        const inp = document.getElementById("histChatFilter");
        if (inp) inp.value = "";
        _applyChatFilter("");
      });
    }

    setupHistorySettings();

    // Load the cap into the settings input on startup.
    setTimeout(_loadCapToSettings, 200);
  }

  function _applyChatFilter(raw) {
    const next = String(raw || "").trim();
    if (next === _chatFilter) return;
    _chatFilter = next;
    loadHistory();
  }

  // Expose
  window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
  window.__RUNCTX_POPUP__.setupHistoryTab = setupHistoryTab;
  window.__RUNCTX_POPUP__.loadHistory = loadHistory;
  window.__RUNCTX_POPUP__.setChatFilter = _applyChatFilter;
  window.__RUNCTX_POPUP__.getChatFilter = () => _chatFilter;
})();
