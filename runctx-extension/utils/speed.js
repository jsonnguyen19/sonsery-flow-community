window.__RUNCTX__ = window.__RUNCTX__ || {};

// ============================================================
// SPEED MULTIPLIER (content script side)
// ============================================================
// Reads envSettings.speedMode from chrome.storage and turns it into a
// multiplier. normal keeps original timing. Live-updates when the
// user changes the setting, so no tab reload is required.
//
// ⚠️ SPEED_FACTORS is defined ONLY in utils/speed-config.js
// (loaded BEFORE this file). Do not hard-code it again here.

const _SPEED_CFG = window.__RUNCTX_SPEED__;
if (!_SPEED_CFG) {
  throw new Error("[speed.js] utils/speed-config.js must be loaded before utils/speed.js");
}

const SPEED_FACTORS = _SPEED_CFG.SPEED_FACTORS;
const normalizeSpeedMode = _SPEED_CFG.normalizeSpeedMode;
const factorFromMode = _SPEED_CFG.getSpeedFactorFromMode;
const isBypassMode = _SPEED_CFG.isBypass;

let currentSpeedFactor = SPEED_FACTORS[_SPEED_CFG.DEFAULT_SPEED_MODE];

async function loadSpeedFactor() {
  try {
    const data = await chrome.storage.local.get(["envSettings", "speedMode"]);
    const mode = data.speedMode || data.envSettings?.speedMode || _SPEED_CFG.DEFAULT_SPEED_MODE;
    currentSpeedFactor = factorFromMode(mode);
  } catch {
    currentSpeedFactor = SPEED_FACTORS[_SPEED_CFG.DEFAULT_SPEED_MODE];
  }
  return currentSpeedFactor;
}

// Kick off the initial load (fire-and-forget).
loadSpeedFactor();

// Live update on storage change.
if (chrome?.storage?.onChanged) {
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    if (changes.speedMode) {
      currentSpeedFactor = factorFromMode(changes.speedMode.newValue);
    } else if (changes.envSettings) {
      const mode = changes.envSettings.newValue?.speedMode || _SPEED_CFG.DEFAULT_SPEED_MODE;
      currentSpeedFactor = factorFromMode(mode);
    }
  });
}

window.__RUNCTX__.Speed = {
  getFactor: () => currentSpeedFactor,
  // scale(ms) with veryFast (factor 0) -> returns 0 (bypass every delay).
  scale: (ms) => Math.round(ms * currentSpeedFactor),
  // True when the current mode is a bypass (delay = 0).
  isBypass: () => currentSpeedFactor === 0,
  normalizeSpeedMode,
  factorFromMode,
  isBypassMode,
  loadSpeedFactor,
};
