window.__RUNCTX__ = window.__RUNCTX__ || {};

window.__RUNCTX__.Logger = {
  debug(...args) {
    console.debug("[Sonsery Flow]", ...args);
  },

  info(...args) {
    console.info("[Sonsery Flow]", ...args);
  },

  warn(...args) {
    console.warn("[Sonsery Flow]", ...args);
  },

  error(...args) {
    console.error("[Sonsery Flow]", ...args);
  },
};
