// ============================================================
// SHARED HELPERS
// ============================================================

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

// Auto-collapse the site sidebar (if any) so the web content and the
// extension side panel can be used side-by-side without overlap.
// Uses the adapter registry of the content script.
async function autoCollapseSidebar() {
  try {
    const tab = await getActiveTab();
    if (!tab?.id || !tab.url) return false;

    const supported =
      tab.url.includes("chatgpt.com") ||
      tab.url.includes("claude.ai") ||
      tab.url.includes("gemini.google.com") ||
      tab.url.includes("chat.deepseek.com");
    if (!supported) return false;

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const registry = window.__RUNCTX__?.AdapterRegistry;
        if (!registry || typeof registry.collapseSidebar !== "function") return false;
        return registry.collapseSidebar();
      },
    });

    return Boolean(results?.[0]?.result);
  } catch (e) {
    console.warn("[popup] autoCollapseSidebar failed:", e);
    return false;
  }
}

async function toastInTab(message, variant = "info") {
  const state = await chrome.storage.local.get(["showToasts"]);
  const showToasts = state.showToasts !== false;
  if (!showToasts) return;
  const tab = await getActiveTab();
  if (!tab?.id) return;
  chrome.scripting
    .executeScript({
      target: { tabId: tab.id },
      func: (msg, v) => window.__RUNCTX__?.showToast?.(msg, v),
      args: [message, variant],
    })
    .catch(() => {});
}

async function runInTab(func, args = []) {
  const tab = await getActiveTab();
  const supported =
    tab.url &&
    (tab.url.includes("chatgpt.com") ||
      tab.url.includes("claude.ai") ||
      tab.url.includes("gemini.google.com") ||
      tab.url.includes("chat.deepseek.com"));
  if (!supported) {
    toastInTab("❌ Not on supported AI site", "error");
    return null;
  }
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func,
    args,
  });
  return results?.[0]?.result ?? null;
}

async function injectContext(tabId, contextText) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (text) => {
        // Prefer DomTransport -> goes through AdapterRegistry.getChatInput()
        // (native setter + beforeinput/input/change/keyup). Required for
        // React controlled composers (ChatGPT, Claude, Gemini, DeepSeek).
        const transport = window.__RUNCTX__?.DomTransport;
        if (transport?.inject) {
          const ok = transport.inject(text);
          if (ok) return true;
        }

        // Fallback: generic selectors (old behavior for sites with no
        // matching adapter or when DomTransport fails).
        const selectors = [
          'div[contenteditable="true"]',
          "textarea",
          '[contenteditable="true"]',
          "#prompt-textarea",
          '[data-testid="prompt-textarea"]',
        ];

        let target = null;
        for (const selector of selectors) {
          target = document.querySelector(selector);
          if (target) break;
        }

        if (!target) {
          navigator.clipboard.writeText(text).catch(() => {});
          return false;
        }

        target.focus();

        if (target.tagName === "TEXTAREA") {
          target.value = text;
          target.dispatchEvent(new Event("input", { bubbles: true }));
        } else {
          target.textContent = text;
          target.dispatchEvent(
            new InputEvent("input", {
              bubbles: true,
              inputType: "insertText",
              data: text,
            })
          );
        }
        return true;
      },
      args: [contextText],
    });

    return results?.[0]?.result || false;
  } catch (e) {
    console.error("Context injection error:", e);
    return false;
  }
}

async function getCurrentInputContent(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // Prefer the current site's adapter (ChatGPT/Claude/Gemini/DeepSeek).
        let target = null;
        try {
          target = window.__RUNCTX__?.AdapterRegistry?.getChatInput?.() || null;
        } catch {
          target = null;
        }

        // Fallback: generic selectors (old behavior).
        if (!target) {
          const selectors = [
            'div[contenteditable="true"]',
            "textarea",
            '[contenteditable="true"]',
            "#prompt-textarea",
            '[data-testid="prompt-textarea"]',
          ];
          for (const selector of selectors) {
            target = document.querySelector(selector);
            if (target) break;
          }
        }

        if (!target) return "";

        if (target.tagName === "TEXTAREA") {
          return target.value || "";
        } else {
          return target.textContent || "";
        }
      },
    });

    return results?.[0]?.result || "";
  } catch (e) {
    console.error("Get current content error:", e);
    return "";
  }
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.getActiveTab = getActiveTab;
window.__RUNCTX_POPUP__.autoCollapseSidebar = autoCollapseSidebar;
window.__RUNCTX_POPUP__.toastInTab = toastInTab;
window.__RUNCTX_POPUP__.runInTab = runInTab;
window.__RUNCTX_POPUP__.injectContext = injectContext;
window.__RUNCTX_POPUP__.getCurrentInputContent = getCurrentInputContent;
