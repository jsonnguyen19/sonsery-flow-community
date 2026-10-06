window.__RUNCTX__ = window.__RUNCTX__ || {};
window.__RUNCTX__.AppAdapters = window.__RUNCTX__.AppAdapters || {};

function isVisible(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  return (
    rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none"
  );
}

function isEnabledButton(el) {
  if (!el || !isVisible(el)) return false;
  return (
    !el.disabled &&
    el.getAttribute("aria-disabled") !== "true" &&
    el.getAttribute("data-disabled") !== "true" &&
    !el.classList.contains("disabled")
  );
}

// ============================================================
// CLAUDE ADAPTER
// ============================================================
// Composer detection + busy/send helpers. Anything appended at the bottom of
// this file must live inside marker comments, and nothing outside those
// markers may reference identifiers defined inside them.

window.__RUNCTX__.AppAdapters.claude = {
  matches: () => location.hostname.includes("claude.ai"),

  // Conversation id from the URL: /chat/<uuid> -> <uuid>.
  getSessionId: () => (location.pathname.match(/\/chat\/([a-z0-9-]+)/i) || [])[1] || null,

  getChatInput: () => {
    // Generic fallback selector list. It may be overridden at the bottom of
    // this file (via Object.assign) with a ProseMirror-anchored selector.
    const selectors = [
      'div.ProseMirror[contenteditable="true"]',
      'div[contenteditable="true"][enterkeyhint]',
      'div[contenteditable="true"][role="textbox"]',
      "textarea",
      '[contenteditable="true"]',
    ];
    return selectors
      .map((selector) => Array.from(document.querySelectorAll(selector)).find(isVisible))
      .find(Boolean);
  },

  getBusyReason: () => {
    const busySelectors = [
      'button[aria-label*="Stop"]',
      'button[aria-label*="Cancel"]',
      'button[aria-label*="Interrupt"]',
      '[data-testid*="stop"] button',
      '[data-testid*="cancel"] button',
    ];

    const isBusy = busySelectors.some((selector) =>
      Array.from(document.querySelectorAll(selector)).some(isEnabledButton)
    );
    return isBusy ? "Claude is still processing input" : "";
  },

  getSendButton: () => {
    const selectors = [
      'button[aria-label="Send Message"]',
      'button[aria-label="Send message"]',
      'button[aria-label*="Send"]',
      '[data-testid="send-button"]',
      'button[type="submit"]',
    ];

    return selectors
      .map((selector) => Array.from(document.querySelectorAll(selector)).find(isEnabledButton))
      .find(Boolean);
  },
};
