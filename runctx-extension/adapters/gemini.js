window.__RUNCTX__ = window.__RUNCTX__ || {};
window.__RUNCTX__.AppAdapters = window.__RUNCTX__.AppAdapters || {};

window.__RUNCTX__.AppAdapters.gemini = {
  matches: () => location.hostname.includes("gemini.google.com"),

  getChatInput: () => {
    const selectors = [
      'div.ql-editor[contenteditable="true"]',
      'rich-textarea div[contenteditable="true"]',
      'div[contenteditable="true"][aria-label*="Enter a prompt"]',
      'div[contenteditable="true"][aria-label*="Message"]',
      "textarea",
    ];

    return selectors.map((selector) => document.querySelector(selector)).find(Boolean);
  },

  getBusyReason: () => {
    const busySelectors = [
      'button[aria-label*="Stop"]',
      'button[aria-label*="Cancel"]',
      'button[aria-label*="Pause"]',
    ];

    const isBusy = busySelectors.some((selector) => document.querySelector(selector));
    return isBusy ? "Gemini is still processing input" : "";
  },

  getSendButton: () => {
    const selectors = [
      '[data-test-id="send-button-container"] gem-icon-button.submit.has-input button',
      '[data-test-id="send-button-container"] gem-icon-button[aria-disabled="false"] button',
      "gem-icon-button.send-button.submit.has-input button",
      'button[aria-label*="Gửi tin nhắn"]',
      'button[aria-label*="Send message"]',
      'button[aria-label*="Send"]',
      'button[aria-label*="Submit"]',
      'button[type="submit"]',
    ];

    return selectors
      .map((selector) => document.querySelector(selector))
      .find(
        (el) =>
          el &&
          !el.disabled &&
          el.closest("gem-icon-button")?.getAttribute("aria-disabled") !== "true"
      );
  },
};
