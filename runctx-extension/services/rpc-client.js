window.__RUNCTX__ = window.__RUNCTX__ || {};

// ============================================================
// RPC CLIENT
// ============================================================
// Thin wrapper around HttpBridgeTransport.callRpc to call read tools
// (stat, list, tree, search, grep) from the UI.
//
// No heavy abstraction: one generic function + a thin wrapper per tool.
// Wrappers return the raw response { ok, status, data, error } so the
// caller decides what to do.

window.__RUNCTX__.RpcClient = {
  /**
   * Generic RPC call.
   * @param {string} tool
   * @param {object} params
   * @returns {Promise<{ok:boolean,status:number,data:object|null,error?:string}>}
   */
  call(tool, params = {}) {
    return window.__RUNCTX__.HttpBridgeTransport.callRpc(tool, params);
  },

  // ===== Thin wrappers =====

  readFile(path, { start, end } = {}) {
    const params = { path };
    if (typeof start === "number") params.start = start;
    if (typeof end === "number") params.end = end;
    return this.call("read", params);
  },

  writeFile(path, content) {
    return this.call("write", { files: [{ path, content }] });
  },

  // ===== Payload history =====

  getHistory(limit = 50, offset = 0, chatId = null) {
    const params = { limit, offset };
    if (chatId) params.chat_id = chatId;
    return this.call("get_history", params);
  },

  getHistoryDetail(id, ts) {
    const params = { payload_id: id };
    if (typeof ts === "number") params.ts = ts;
    return this.call("get_history_detail", params);
  },

  clearHistory() {
    return this.call("clear_history", {});
  },

  setHistoryCap(cap) {
    return this.call("set_history_cap", { cap });
  },

  stat(path) {
    return this.call("stat", { path });
  },

  list(path = ".") {
    return this.call("list", { path });
  },

  tree(path = ".") {
    return this.call("tree", { path });
  },

  search(query, { path = ".", mode = "content" } = {}) {
    return this.call("search", { query, path, mode });
  },

  grep(query, { path = "." } = {}) {
    return this.call("grep", { query, path });
  },
};
