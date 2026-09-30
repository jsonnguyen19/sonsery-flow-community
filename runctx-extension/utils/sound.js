window.__RUNCTX__ = window.__RUNCTX__ || {};

// Path inside the extension → resolves to chrome-extension://<id>/assets/sounds/ding.wav
const RESULT_SOUND_PATH = "assets/sounds/ding.wav";

// Cache a single Audio instance to avoid creating a new one on every play (less GC + allows replay).
let _resultAudio = null;

function getResultAudio() {
  if (_resultAudio) return _resultAudio;
  try {
    const url = chrome.runtime.getURL(RESULT_SOUND_PATH);
    _resultAudio = new Audio(url);
    _resultAudio.preload = "auto";
    _resultAudio.addEventListener("error", () => {
      console.warn("[sound] failed to load", RESULT_SOUND_PATH);
    });
  } catch (e) {
    console.warn("[sound] cannot create Audio:", e);
    _resultAudio = null;
  }
  return _resultAudio;
}

window.__RUNCTX__.shouldPlayResultSound = async function () {
  const state = await chrome.storage.local.get(["playResultSound"]);
  return state.playResultSound === true;
};

window.__RUNCTX__.playResultSound = async function () {
  try {
    if (!(await window.__RUNCTX__.shouldPlayResultSound())) return;
    const audio = getResultAudio();
    if (!audio) return;
    // Reset so it can play again even while mid-play.
    audio.currentTime = 0;
    const p = audio.play();
    if (p && typeof p.catch === "function") {
      p.catch((err) => {
        // AbortError is expected when a previous play() was interrupted by a
        // newer play() (results arriving back-to-back) -> skip, do not warn.
        if (err && err.name === "AbortError") return;
        console.warn("[sound] play rejected:", err);
      });
    }
  } catch (e) {
    console.warn("[sound] playResultSound failed:", e);
  }
};
