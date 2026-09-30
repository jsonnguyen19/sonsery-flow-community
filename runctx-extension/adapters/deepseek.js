window.__RUNCTX__ = window.__RUNCTX__ || {};
window.__RUNCTX__.AppAdapters = window.__RUNCTX__.AppAdapters || {};

window.__RUNCTX__.AppAdapters.deepseek = {
  matches: () => location.hostname.includes("chat.deepseek.com"),
  // => caret is computed via selectionStart/End, insert via setRangeText/value.
  // => getCaretRect is overridden to anchor the dropdown to the caret inside the textarea.
  getChatInput: () => document.querySelector("textarea"),

  /**
   * Compute the caret rect inside a textarea by measuring the text before it.
   * Returns a DOMRect-like {top,left,bottom,right,width,height}.
   */
  getCaretRect(composer) {
    if (!composer || composer.tagName !== "TEXTAREA") {
      return null;
    }
    try {
      const pos = composer.selectionStart ?? 0;
      const before = composer.value.slice(0, pos);
      const after = composer.value.slice(pos);

      // Mirror div to measure the caret position.
      const mirror = document.createElement("div");
      const cs = window.getComputedStyle(composer);
      const props = [
        "boxSizing",
        "width",
        "height",
        "overflowX",
        "overflowY",
        "borderTopWidth",
        "borderRightWidth",
        "borderBottomWidth",
        "borderLeftWidth",
        "paddingTop",
        "paddingRight",
        "paddingBottom",
        "paddingLeft",
        "fontStyle",
        "fontVariant",
        "fontWeight",
        "fontStretch",
        "fontSize",
        "fontFamily",
        "lineHeight",
        "textAlign",
        "textTransform",
        "textIndent",
        "letterSpacing",
        "wordSpacing",
        "whiteSpace",
        "wordWrap",
        "wordBreak",
      ];
      for (const p of props) mirror.style[p] = cs[p];
      mirror.style.position = "absolute";
      mirror.style.visibility = "hidden";
      mirror.style.whiteSpace = "pre-wrap";
      mirror.style.wordWrap = "break-word";
      mirror.style.overflow = "hidden";
      mirror.style.width = cs.width;

      const span = document.createElement("span");
      span.textContent = before.length ? before.slice(-1) : " ";
      // Place the text before the caret + the marker.
      mirror.textContent = before;
      const marker = document.createElement("span");
      marker.textContent = "\u200b";
      mirror.appendChild(marker);
      mirror.appendChild(document.createTextNode(after));
      document.body.appendChild(mirror);

      const composerRect = composer.getBoundingClientRect();
      const markerRect = marker.getBoundingClientRect();
      const mirrorRect = mirror.getBoundingClientRect();
      const scrollTop = composer.scrollTop || 0;

      // If the caret is outside the visible area -> fall back to the textarea origin.
      let top = composerRect.top + (markerRect.top - mirrorRect.top) - scrollTop;
      let left = composerRect.left + (markerRect.left - mirrorRect.left);

      // Clamp inside the textarea.
      const minTop = composerRect.top;
      const maxTop = composerRect.bottom - 18;
      if (top < minTop) top = minTop;
      if (top > maxTop) top = maxTop;
      if (left < composerRect.left) left = composerRect.left;
      if (left > composerRect.right) left = composerRect.right;

      document.body.removeChild(mirror);
      return {
        top,
        left,
        bottom: top + 18,
        right: left,
        width: 0,
        height: 18,
      };
    } catch {
      return null;
    }
  },

  /**
   * Insert text into the textarea at the caret (selectionStart), keeping the existing text.
   * Returns true on success.
   */
  insertText(composer, text) {
    if (!composer || composer.tagName !== "TEXTAREA") return false;
    try {
      const start = composer.selectionStart ?? composer.value.length;
      const end = composer.selectionEnd ?? start;
      const before = composer.value.slice(0, start);
      const after = composer.value.slice(end);
      composer.value = before + text + after;
      const caret = start + text.length;
      composer.selectionStart = caret;
      composer.selectionEnd = caret;
      composer.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: text,
        })
      );
      return true;
    } catch {
      return false;
    }
  },

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
