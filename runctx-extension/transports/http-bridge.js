window.__RUNCTX__ = window.__RUNCTX__ || {};

window.__RUNCTX__.HttpBridgeTransport = {
  async getResult() {
    const logger = window.__RUNCTX__.Logger;

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "RUNCTX_BRIDGE_GET_RESULT" }, (res) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (res?.error) {
            reject(new Error(res.error));
          } else {
            resolve(res);
          }
        });
      });

      const data = response.data;

      if (!data?.result || !data?.hash) {
        return null;
      }

      logger.info("Bridge result received", {
        hash: data.hash,
        length: String(data.result).length,
      });

      return {
        hash: String(data.hash),
        result: String(data.result),
      };
    } catch (error) {
      logger.error("Bridge getResult failed", error);
      return null;
    }
  },

  async consumeResult() {
    const logger = window.__RUNCTX__.Logger;

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "RUNCTX_BRIDGE_CONSUME_RESULT" }, (res) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (res?.error) {
            reject(new Error(res.error));
          } else {
            resolve(res);
          }
        });
      });

      if (!response.ok) {
        logger.warn("Bridge consume failed", response.status);
        return false;
      }

      logger.info("Bridge result consumed");
      return true;
    } catch (error) {
      logger.error("Bridge consume failed", error);
      return false;
    }
  },

  /**
   * Call a Bridge RPC: ask the backend directly and get the result.
   * Returns { ok, status, data } or { error } on transport failure.
   *
   * @param {string} tool  - e.g. "git", "stat", "list", "tree", "search", "grep"
   * @param {object} params - tool params (relative path, query, action...)
   */
  async callRpc(tool, params = {}) {
    const logger = window.__RUNCTX__.Logger;

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "RUNCTX_BRIDGE_RPC", tool, params }, (res) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (res?.error) {
            reject(new Error(res.error));
          } else {
            resolve(res);
          }
        });
      });

      logger.info("Bridge RPC finished", { tool, status: response.status });
      return response;
    } catch (error) {
      logger.error("Bridge RPC failed", error);
      return { ok: false, status: 0, data: null, error: error.message };
    }
  },
};
