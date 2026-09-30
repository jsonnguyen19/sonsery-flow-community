// ============================================================
// AUTOMATION SPEED (popup side)
// ============================================================
// Speed multiplier for the popup UI (load/save speed mode).
//
// ⚠️ SPEED_FACTORS is defined ONLY in utils/speed-config.js.
// This file just reads from window.__RUNCTX_SPEED__.

const _SPEED_CFG = window.__RUNCTX_SPEED__;
if (!_SPEED_CFG) {
  throw new Error("[popup/speed.js] utils/speed-config.js must be loaded first");
}

const SPEED_MODE_KEY = "speedMode";
const DEFAULT_SPEED_MODE = _SPEED_CFG.DEFAULT_SPEED_MODE;
const SPEED_FACTORS = _SPEED_CFG.SPEED_FACTORS;
const normalizeSpeedMode = _SPEED_CFG.normalizeSpeedMode;
const getSpeedFactorFromMode = _SPEED_CFG.getSpeedFactorFromMode;

async function getSpeedMode() {
  const data = await chrome.storage.local.get([SPEED_MODE_KEY]);
  return normalizeSpeedMode(data[SPEED_MODE_KEY]);
}

async function getSpeedFactor() {
  return getSpeedFactorFromMode(await getSpeedMode());
}

async function saveSpeedMode(mode) {
  const normalized = normalizeSpeedMode(mode);
  await chrome.storage.local.set({ [SPEED_MODE_KEY]: normalized });
  return normalized;
}

// Expose to window for other popup scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.SPEED_MODE_KEY = SPEED_MODE_KEY;
window.__RUNCTX_POPUP__.DEFAULT_SPEED_MODE = DEFAULT_SPEED_MODE;
window.__RUNCTX_POPUP__.SPEED_FACTORS = SPEED_FACTORS;
window.__RUNCTX_POPUP__.normalizeSpeedMode = normalizeSpeedMode;
window.__RUNCTX_POPUP__.getSpeedFactorFromMode = getSpeedFactorFromMode;
window.__RUNCTX_POPUP__.getSpeedMode = getSpeedMode;
window.__RUNCTX_POPUP__.getSpeedFactor = getSpeedFactor;
window.__RUNCTX_POPUP__.saveSpeedMode = saveSpeedMode;
