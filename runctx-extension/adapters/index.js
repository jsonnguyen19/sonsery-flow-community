window.__RUNCTX__ = window.__RUNCTX__ || {};

window.__RUNCTX__.AdapterRegistry = {
  // This repo ships every registered adapter; there is no runtime plan gate.
  _getVisibleAdapters() {
    return window.__RUNCTX__.AppAdapters || {};
  },

  getCurrentAdapter() {
    const adapters = this._getVisibleAdapters();
    return Object.values(adapters).find((adapter) => adapter.matches()) || adapters.fallback;
  },

  // Return the matching adapter key (e.g. "chatgpt", "claude"). Fallback -> "unknown".
  getCurrentRole() {
    const adapters = this._getVisibleAdapters();
    for (const [key, adapter] of Object.entries(adapters)) {
      if (key === "fallback") continue;
      try {
        if (adapter.matches?.()) return key;
      } catch {
        // ignore adapter error, try the next one
      }
    }
    return "unknown";
  },

  // Conversation id for the active adapter (host-specific URL pattern).
  // Each adapter declares its own getSessionId(); the fallback adapter has
  // none, so this returns null on an unknown host. Used to tag history rows
  // with the conversation they came from.
  getCurrentSessionId() {
    const adapter = this.getCurrentAdapter();
    try {
      return adapter?.getSessionId?.() || null;
    } catch {
      return null;
    }
  },

  getChatInput() {
    const adapter = this.getCurrentAdapter();
    const adapterInput = adapter.getChatInput?.();

    if (adapterInput) return adapterInput;

    const selectors = [
      'div.ProseMirror[contenteditable="true"]',
      '[data-testid="prompt-textarea"]',
      "#prompt-textarea",
      "textarea",
      '[contenteditable="true"]',
    ];

    return selectors.map((selector) => document.querySelector(selector)).find(Boolean);
  },

  pasteTextToChat(text) {
    const target = this.getChatInput();
    if (!target) return false;

    // Force focus for contenteditable elements (Claude) even without tab focus
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    target.focus?.({ preventScroll: true });

    // For Claude's contenteditable, trigger click to activate composer
    if (target.isContentEditable) {
      target.click();
    }

    if (target.tagName === "TEXTAREA") {
      target.value = text;
      target.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }

    const dataTransfer = new DataTransfer();
    dataTransfer.setData("text/plain", text);

    const pasteEvent = new ClipboardEvent("paste", {
      bubbles: true,
      cancelable: true,
      clipboardData: dataTransfer,
    });

    const accepted = target.dispatchEvent(pasteEvent);

    if (!target.textContent?.includes(text.slice(0, 20))) {
      target.textContent = text;
      target.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: text,
        })
      );
    }

    // Ensure input event fires after paste for Claude
    target.dispatchEvent(new Event("input", { bubbles: true }));

    return accepted || Boolean(target.textContent?.trim());
  },

  async waitForSendButton({ timeoutMs = 15000, intervalMs = 500 } = {}) {
    const adapter = this.getCurrentAdapter();
    const startedAt = Date.now();
    let hasShownWaitingToast = false;
    // Scale the poll interval with the speed setting. The hard timeout is
    // intentionally NOT scaled to avoid premature false negatives on Fast.
    const scaledIntervalMs = window.__RUNCTX__.Speed?.scale(intervalMs) ?? intervalMs;

    while (Date.now() - startedAt < timeoutMs) {
      const busyReason = adapter.getBusyReason?.() || "";

      if (busyReason) {
        if (!hasShownWaitingToast) {
          if (await window.__RUNCTX__.shouldShowToasts()) {
            window.__RUNCTX__.showToast(`${busyReason}. Waiting to send...`, "warn");
          }
          hasShownWaitingToast = true;
        }
        await window.__RUNCTX__.sleep(scaledIntervalMs);
        continue;
      }

      const button = adapter.getSendButton?.();
      if (button) return button;

      await window.__RUNCTX__.sleep(scaledIntervalMs);
    }

    return null;
  },

  async clickSendButtonWhenReady() {
    const button = await this.waitForSendButton();
    if (!button) return false;

    button.click();
    return true;
  },

  // Collapse the site sidebar if the current adapter supports it.
  // Returns true if a collapse click was performed.
  collapseSidebar() {
    const adapter = this.getCurrentAdapter();
    if (typeof adapter.collapseSidebar !== "function") return false;
    try {
      return Boolean(adapter.collapseSidebar());
    } catch (e) {
      window.__RUNCTX__.Logger?.warn("collapseSidebar failed:", e);
      return false;
    }
  },
};
