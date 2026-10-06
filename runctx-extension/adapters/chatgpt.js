window.__RUNCTX__ = window.__RUNCTX__ || {};
window.__RUNCTX__.AppAdapters = window.__RUNCTX__.AppAdapters || {};

// ============================================================
// CHATGPT ADAPTER
// ============================================================
// Composer: ProseMirror `div.ProseMirror#prompt-textarea[contenteditable="true"]`.

window.__RUNCTX__.AppAdapters.chatgpt = {
  matches: () => location.hostname.includes("chatgpt.com"),

  // Conversation id from the URL: /c/<uuid> -> <uuid>.
  getSessionId: () => (location.pathname.match(/\/c\/([a-z0-9-]+)/i) || [])[1] || null,

  getBusyReason: () => {
    const busySelectors = [
      '[data-testid="stop-button"]',
      'button[aria-label*="Stop"]',
      'button[aria-label*="Pause"]',
      'button[aria-label*="Cancel"]',
    ];

    const isBusy = busySelectors.some((selector) => document.querySelector(selector));
    return isBusy ? "ChatGPT is still processing input" : "";
  },

  getSendButton: () => {
    const selectors = [
      '[data-testid="send-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send message"]',
    ];

    return selectors
      .map((selector) => document.querySelector(selector))
      .find((el) => el && !el.disabled && el.getAttribute("aria-disabled") !== "true");
  },
};
