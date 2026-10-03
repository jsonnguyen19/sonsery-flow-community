// ============================================================
// INJECT CONTEXT + TOASTS TOGGLE
// ============================================================
function applyIdProtocol(text) {
  const body = String(text == null ? "" : text);
  const initId = Date.now();
  const patterns = [/<unix_ms_now>/g, /<unix_ms>/g, /<unix_timestamp_ms>/g];
  let out = body;
  for (const re of patterns) {
    out = out.replace(re, String(initId));
    re.lastIndex = 0;
  }
  const directive = [
    "",
    "========================================",
    "INIT_ID = " + initId,
    "",
  ].join("\n");
  return out + directive;
}

function setupInjectButton() {
  const injectBtn = document.getElementById("injectBtn");
  const injectSelect = document.getElementById("injectSelect");

  if (!injectBtn) return;

  injectBtn.addEventListener("click", async () => {
    const tab = await getActiveTab();
    if (!tab?.id) {
      toastInTab("No active tab", "error");
      return;
    }

    const selected = injectSelect?.value || "agentctx";
    const settings = await getEnvSettings();
    const envContext = buildEnvironmentContext(settings);

    let contextText = "";
    let label = "";

    contextText = AGENTCTX_CONTENT;
    label = "Agentctx injected";
    if (!contextText || contextText.trim() === "") {
      contextText = `You are an AI assistant. Help write code in a local project via the runctx workflow.

WHEN INTERACTING WITH THE PROJECT:
- Use runctx payload (batch/edit/write)
- Do not guess file contents, imports, paths
- Always investigate before implementing
- After the code block write "runctx"

When the task is complete:
{
  "type": "done"
}`;
      toastInTab("⚠️ AGENTCTX_CONTENT empty, using fallback", "warn");
    }

    // Append environment context if there are non-auto settings
    if (envContext) {
      contextText = contextText + envContext;
      label += " + env";
    }

    // Inject ID protocol: replace the <unix_ms_now> placeholder with a fixed
    // INIT_ID (Date.now() at inject time) + the +N directive. Runs in the
    // popup context — window.__RUNCTX__ is unavailable, so use an inline
    // function matching id-injector.js (kept in sync).
    contextText = applyIdProtocol(contextText);

    const tokens = estimateTokens(contextText);
    chrome.runtime.sendMessage({
      type: "RUNCTX_TRACK_PAYLOAD",
      payload: contextText,
      label: label,
    });

    const injected = await injectContext(tab.id, contextText);
    if (injected) {
      toastInTab(`${label} (${tokens} tokens)`, "success");
    } else {
      toastInTab(`${label} copied (${tokens} tokens)`, "info");
    }
  });
}

function setupShowToastsToggle() {
  const showToastsToggle = document.getElementById("showToasts");
  if (!showToastsToggle) return;
  showToastsToggle.addEventListener("change", async () => {
    const checked = showToastsToggle.checked;
    await chrome.storage.local.set({ showToasts: checked });
  });
}

async function loadShowToastsState() {
  const state = await chrome.storage.local.get(["showToasts"]);
  const showToasts = state.showToasts !== false;
  const showToastsToggle = document.getElementById("showToasts");
  if (showToastsToggle) {
    showToastsToggle.checked = showToasts;
  }
}

function setupPlayResultSoundToggle() {
  const toggle = document.getElementById("playResultSound");
  if (!toggle) return;
  toggle.addEventListener("change", async () => {
    await chrome.storage.local.set({ playResultSound: toggle.checked });
  });
}

async function loadPlayResultSoundState() {
  const state = await chrome.storage.local.get(["playResultSound"]);
  const enabled = state.playResultSound === true;
  const toggle = document.getElementById("playResultSound");
  if (toggle) {
    toggle.checked = enabled;
  }
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.setupInjectButton = setupInjectButton;
window.__RUNCTX_POPUP__.setupShowToastsToggle = setupShowToastsToggle;
window.__RUNCTX_POPUP__.loadShowToastsState = loadShowToastsState;
window.__RUNCTX_POPUP__.setupPlayResultSoundToggle = setupPlayResultSoundToggle;
window.__RUNCTX_POPUP__.loadPlayResultSoundState = loadPlayResultSoundState;
