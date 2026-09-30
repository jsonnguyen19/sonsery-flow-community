// ============================================================
// SPEED CONFIG — SINGLE SOURCE OF TRUTH
// ============================================================
// ⚠️ THIS IS THE ONLY place that defines speed factors.
// Everywhere (content script, popup, background/service worker) reads
// from window.__RUNCTX_SPEED__ instead of hard-coding its own copy.
//
// Meaning: time multiplier (ms multiplier).
//   slow     = 3.0  -> ~2x slower than normal
//   normal   = 1.5  -> baseline
//   fast     = 0.5  -> ~3x faster than normal
//   veryFast = 0    -> BYPASS speed, drop every delay, send immediately
//
// NOTE: veryFast = 0 is a special sentinel. Any code using SPEED_FACTORS
// must respect the value 0 (do not fall back to a default because 0 is falsy).
// To change it, edit ONLY this file.

(function (global) {
  const SPEED_FACTORS = {
    slow: 3.0,
    normal: 1.5,
    fast: 0.5,
    veryFast: 0,
  };

  const DEFAULT_SPEED_MODE = "normal";

  function normalizeSpeedMode(mode) {
    // Use hasOwnProperty to avoid being fooled by a falsy value (0).
    return Object.prototype.hasOwnProperty.call(SPEED_FACTORS, mode) ? mode : DEFAULT_SPEED_MODE;
  }

  function getSpeedFactorFromMode(mode) {
    return SPEED_FACTORS[normalizeSpeedMode(mode)];
  }

  // True when the mode is a bypass (no speed applied, drop every delay).
  function isBypass(mode) {
    return getSpeedFactorFromMode(mode) === 0;
  }

  // Base delay (ms) between result inject and auto-send, before scaling.
  // Used to space out requests and reduce rate limits.
  const RESULT_TO_SEND_BASE_MS = 800;

  global.__RUNCTX_SPEED__ = {
    SPEED_FACTORS,
    DEFAULT_SPEED_MODE,
    normalizeSpeedMode,
    getSpeedFactorFromMode,
    isBypass,
    RESULT_TO_SEND_BASE_MS,
  };
})(typeof window !== "undefined" ? window : self);
