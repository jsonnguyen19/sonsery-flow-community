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

window.__RUNCTX__.AppAdapters.claude = {
  matches: () => location.hostname.includes("claude.ai"),

  getChatInput: () => {
    const selectors = [
      'div[contenteditable="true"][enterkeyhint]',
      'div[contenteditable="true"][role="textbox"]',
      'div[contenteditable="true"][aria-label*="Message"]',
      'div[contenteditable="true"][aria-label*="Talk"]',
      'div.ProseMirror[contenteditable="true"]',
      '[data-testid="chat-input"] div[contenteditable="true"]',
      '[data-testid="composer"] div[contenteditable="true"]',
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
