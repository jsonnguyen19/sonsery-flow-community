window.__RUNCTX__ = window.__RUNCTX__ || {};
window.__RUNCTX__.AppAdapters = window.__RUNCTX__.AppAdapters || {};

window.__RUNCTX__.AppAdapters.deepseek = {
  matches: () => location.hostname.includes("chat.deepseek.com"),

  getBusyReason: () => {
    const busySelectors = [
      'div[role="button"].ds-button[aria-label*="Stop"]',
      'div[role="button"].ds-button[aria-label*="Cancel"]',
      'button[aria-label*="Stop"]',
      'button[aria-label*="Cancel"]',
    ];

    const isBusy = busySelectors.some((selector) => document.querySelector(selector));
    return isBusy ? "DeepSeek is still processing input" : "";
  },

  getSendButton: () => {
    const selectors = [
      'div[role="button"].ds-button--primary.ds-button--filled.ds-button--circle',
      'div[role="button"].ds-button--primary.ds-button--icon-relative-m',
      'div[role="button"].ds-button--filled.ds-button--circle',
      'button[aria-label*="Send"]',
      'button[type="submit"]',
    ];

    return selectors
      .map((selector) => document.querySelector(selector))
      .find(
        (el) =>
          el &&
          el.getAttribute("aria-disabled") !== "true" &&
          !el.classList.contains("ds-button--disabled")
      );
  },

  // Detect whether the DeepSeek sidebar is currently expanded.
  // The sidebar is collapsed state when the collapse button still exists
  // but the sidebar container is hidden. We detect expansion by checking
  // the presence of the collapse button whose icon is the "panel" glyph.
  // The toggle button is always present (with the panel glyph) but only
  // *visible* while the sidebar is expanded. So: if the toggle button is
  // visible → sidebar is expanded; if not → sidebar is collapsed.
  getSidebarState: () => {
    const toggle = window.__RUNCTX__.AppAdapters.deepseek.getSidebarToggle();
    if (!toggle) return "unknown";
    const rect = toggle.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 ? "expanded" : "collapsed";
  },

  // Find the sidebar collapse/expand toggle button.
  //
  // The real toggle (confirmed via user click capture) is:
  //   div[role="button"].ds-button.ds-button--iconLabelTertiary
  // carrying the "panel" glyph (9.67272 / 0.522841). It is NOT one of the
  // 4 iconLabelPrimary buttons in the header.
  getSidebarToggle: () => {
    const PANEL_GLYPH = ["9.67272", "0.522841"];

    const candidates = Array.from(
      document.querySelectorAll('div[role="button"].ds-button--iconLabelTertiary')
    );

    const isPanelGlyph = (btn) => {
      const d = btn.querySelector("svg path")?.getAttribute("d") || "";
      return PANEL_GLYPH.every((p) => d.includes(p));
    };

    const isVisible = (el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };

    // Prefer a visible toggle (sidebar expanded).
    for (const btn of candidates) {
      if (isPanelGlyph(btn) && isVisible(btn)) return btn;
    }
    // Fallback: any matching toggle, even if hidden.
    for (const btn of candidates) {
      if (isPanelGlyph(btn)) return btn;
    }

    return null;
  },

  // Collapse the sidebar if it is currently expanded.
  // Returns true if a click was performed, false otherwise.
  collapseSidebar: () => {
    const state = window.__RUNCTX__.AppAdapters.deepseek.getSidebarState();
    if (state !== "expanded") return false;

    const btn = window.__RUNCTX__.AppAdapters.deepseek.getSidebarToggle();
    if (!btn) return false;

    // DeepSeek (React) may not respond to a plain .click().
    // Dispatch the full pointer + mouse sequence to be safe.
    const fireMouse = (type, extra = {}) => {
      btn.dispatchEvent(
        new MouseEvent(type, {
          bubbles: true,
          cancelable: true,
          view: window,
          ...extra,
        })
      );
    };
    const firePointer = (type) => {
      btn.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          cancelable: true,
          pointerType: "mouse",
          isPrimary: true,
        })
      );
    };

    try {
      firePointer("pointerdown");
      fireMouse("mousedown");
      firePointer("pointerup");
      fireMouse("mouseup");
      fireMouse("click");
      window.__RUNCTX__.Logger?.debug("[DS-collapse] full event sequence dispatched");
    } catch (e) {
      window.__RUNCTX__.Logger?.warn("[DS-collapse] event dispatch failed, fallback .click():", e);
      btn.click();
    }

    return true;
  },
};
