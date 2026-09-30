window.__RUNCTX__ = window.__RUNCTX__ || {};
window.__RUNCTX__.AppAdapters = window.__RUNCTX__.AppAdapters || {};

window.__RUNCTX__.AppAdapters.fallback = {
  matches: () => true,

  getBusyReason: () => "",

  getSendButton: () => {
    const selectors = [
      '[data-testid="send-button"]',
      'button[aria-label*="Send"]',
      'button[type="submit"]',
    ];

    return selectors
      .map((selector) => document.querySelector(selector))
      .find((el) => el && !el.disabled && el.getAttribute("aria-disabled") !== "true");
  },

  // Fallback adapter has no sidebar concept.
  collapseSidebar: () => false,
};
