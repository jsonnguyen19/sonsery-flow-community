// ============================================================
// MANUAL CONTROLS: Copy / Paste / Send / Clear
// ============================================================

function setupManualControls() {
  const copyBtn = document.getElementById("copyBtn");
  const pasteBtn = document.getElementById("pasteBtn");
  const sendBtn = document.getElementById("sendBtn");
  const clearToolsBtn = document.getElementById("clearToolsBtn");

  copyBtn.addEventListener("click", async () => {
    copyBtn.disabled = true;
    const payload = await runInTab(() => {
      const RUNCTX_PAYLOAD_TOOLS = ["shell", "read", "replace", "write"];
      function cleanCodeBlock(text) {
        return text
          .replace(/^```[\w]*\n?/, "")
          .replace(/```$/, "")
          .trim();
      }
      function looksLikeRunctxPayload(text) {
        const payload = cleanCodeBlock(text);
        if (!payload) return false;
        try {
          const parsed = JSON.parse(payload);
          return (
            !!parsed && typeof parsed === "object" && RUNCTX_PAYLOAD_TOOLS.includes(parsed.tool)
          );
        } catch {
          return false;
        }
      }
      function getLatestAssistantMessage() {
        const selectors = ['[data-message-author-role="assistant"]', ".font-claude-response"];
        const messages = selectors.flatMap((s) => Array.from(document.querySelectorAll(s)));
        return messages.at(-1) || null;
      }
      const root = getLatestAssistantMessage() || document;
      const blocks = Array.from(root.querySelectorAll("pre code, pre"))
        .map((node) => cleanCodeBlock(node.innerText || node.textContent || ""))
        .filter(Boolean);
      for (let i = blocks.length - 1; i >= 0; i--) {
        if (looksLikeRunctxPayload(blocks[i])) return blocks[i];
      }
      return null;
    });
    copyBtn.disabled = false;
    if (!payload) {
      toastInTab("No runctx payload found", "warn");
      return;
    }
    try {
      await navigator.clipboard.writeText(payload);
      toastInTab("Payload copied", "success");
    } catch {
      toastInTab("Clipboard write failed", "error");
    }
  });

  pasteBtn.addEventListener("click", async () => {
    pasteBtn.disabled = true;
    let clipText = null;
    try {
      clipText = await navigator.clipboard.readText();
    } catch {
      toastInTab("Clipboard read failed", "error");
      pasteBtn.disabled = false;
      return;
    }
    if (!clipText) {
      toastInTab("Clipboard is empty", "warn");
      pasteBtn.disabled = false;
      return;
    }
    const result = await runInTab(
      (text) => {
        const injected = window.__RUNCTX__?.DomTransport?.inject?.(text);
        if (injected) return "OK";
        const fallback = window.__RUNCTX__?.AdapterRegistry?.pasteTextToChat?.(text);
        return fallback ? "OK_FALLBACK" : "INJECT_FAIL";
      },
      [clipText]
    );
    pasteBtn.disabled = false;
    if (result === "OK" || result === "OK_FALLBACK") {
      toastInTab("Pasted into input", "success");
    } else {
      toastInTab("Could not find chat input", "error");
    }
  });

  sendBtn.addEventListener("click", async () => {
    sendBtn.disabled = true;
    const result = await runInTab(async () => {
      const sent = await window.__RUNCTX__?.AdapterRegistry?.clickSendButtonWhenReady?.();
      return sent ? "OK" : "NOT_FOUND";
    });
    sendBtn.disabled = false;
    if (result === "OK") {
      toastInTab("Message sent", "success");
    } else {
      toastInTab("Send button not found", "error");
    }
  });

  // Update only the .btn-label span so the SVG icon survives loading states.
  const setBtnLabel = (btn, text) => {
    const label = btn.querySelector(".btn-label");
    if (label) label.textContent = text;
    else btn.textContent = text;
  };

  const killWatchctxBtn = document.getElementById("killWatchctxBtn");
  if (killWatchctxBtn) {
    killWatchctxBtn.addEventListener("click", async () => {
      killWatchctxBtn.disabled = true;
      setBtnLabel(killWatchctxBtn, "Killing...");

      try {
        await new Promise((resolve) => {
          chrome.runtime.sendMessage({ type: "RUNCTX_BRIDGE_SHUTDOWN" }, (res) => resolve(res));
        });
        toastInTab("watchctx killed", "success");
      } catch (error) {
        toastInTab("Failed to kill watchctx: " + error.message, "error");
      } finally {
        killWatchctxBtn.disabled = false;
        setBtnLabel(killWatchctxBtn, "Kill watchctx");
      }
    });
  }

  clearToolsBtn.addEventListener("click", async () => {
    clearToolsBtn.disabled = true;
    setBtnLabel(clearToolsBtn, "Resetting...");

    try {
      // 1. Clear clipboard (browser side)
      await navigator.clipboard.writeText("");

      // 2. Clear clipboard in the page via runInTab
      await runInTab(() => {
        try {
          navigator.clipboard.writeText("").catch(() => {});
          return true;
        } catch {
          return false;
        }
      });

      // 3. Clear result from watchctx via the bridge API.
      // Go through the background service worker so it resolves the dynamic port
      // (the bridge may listen on a port other than 8765 if the default is taken).
      try {
        const response = await new Promise((resolve) => {
          chrome.runtime.sendMessage({ type: "RUNCTX_BRIDGE_CONSUME_RESULT" }, (res) =>
            resolve(res)
          );
        });
        if (response?.ok) {
          console.log("✅ watchctx result cleared");
        } else {
          console.warn("⚠️ Failed to clear watchctx result:", response?.status);
        }
      } catch {
        // Bridge might not be running - that's fine, just log
        console.log("ℹ️ watchctx bridge not available (result cleared from storage only)");
      }

      // 4. Clear stored result state in extension
      await chrome.storage.local.remove([
        "payloadCount",
        "resultCount",
        "lastPayloadAt",
        "lastResultAt",
      ]);

      toastInTab("Tools reset (clipboard & result cleared)", "success");

      // 5. Re-render to update UI
      await render();
    } catch (error) {
      toastInTab("Failed to clear: " + error.message, "error");
    } finally {
      clearToolsBtn.disabled = false;
      setBtnLabel(clearToolsBtn, "Reset tools");
    }
  });
}

// Expose to window for other scripts
window.__RUNCTX_POPUP__ = window.__RUNCTX_POPUP__ || {};
window.__RUNCTX_POPUP__.setupManualControls = setupManualControls;
