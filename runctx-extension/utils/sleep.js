window.__RUNCTX__ = window.__RUNCTX__ || {};

window.__RUNCTX__.sleep = function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
};
