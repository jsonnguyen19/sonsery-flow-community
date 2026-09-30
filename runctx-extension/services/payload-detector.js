window.__RUNCTX__ = window.__RUNCTX__ || {};

// ============================================================
// PAYLOAD DETECTOR
// ============================================================
// Pure detection logic: scan code blocks in latest assistant message
// and pick the latest runctx payload.

const RUNCTX_TOOLS = ["shell", "read", "replace", "write"];

// Special payload types registered by feature modules at load time so
// detection is pluggable. The list is empty in this build.
const RUNCTX_SPECIAL_TYPES = [];

function hasRunctxToolDeclaration(payload) {
  // Check for tool-based payload (plus any registered special types)
  const allTools = [...RUNCTX_TOOLS, ...RUNCTX_SPECIAL_TYPES];
  const hasTool = allTools.some((tool) => {
    const jsonToolWithSpace = `"tool": "${tool}"`;
    const jsonToolNoSpace = `"tool":"${tool}"`;
    const singleQuoteToolWithSpace = `'tool': '${tool}'`;
    const singleQuoteToolNoSpace = `'tool':'${tool}'`;
    const yamlTool = new RegExp(`^tool:\\s*${tool}\\s*$`, "m");

    return (
      payload.includes(jsonToolWithSpace) ||
      payload.includes(jsonToolNoSpace) ||
      payload.includes(singleQuoteToolWithSpace) ||
      payload.includes(singleQuoteToolNoSpace) ||
      yamlTool.test(payload)
    );
  });

  // Check for "type": "<special>" payloads (e.g. switch). Empty when no
  // module registered a special type — the some() below then returns false.
  const hasSpecial = RUNCTX_SPECIAL_TYPES.some((type) => {
    const jsonTypeWithSpace = `"type": "${type}"`;
    const jsonTypeNoSpace = `"type":"${type}"`;
    const singleQuoteTypeWithSpace = `'type': '${type}'`;
    const singleQuoteTypeNoSpace = `'type':'${type}'`;
    const yamlType = new RegExp(`^type:\\s*${type}\\s*$`, "m");

    return (
      payload.includes(jsonTypeWithSpace) ||
      payload.includes(jsonTypeNoSpace) ||
      payload.includes(singleQuoteTypeWithSpace) ||
      payload.includes(singleQuoteTypeNoSpace) ||
      yamlType.test(payload)
    );
  });

  return hasTool || hasSpecial;
}

function looksLikeRunctxPayload(text) {
  const payload = window.__RUNCTX__.HashUtils.cleanCodeBlock(text);
  if (!payload) return false;
  if (!(
    payload.includes('"tool"') ||
    payload.includes("'tool'") ||
    /^tool:\\s*/m.test(payload) ||
    payload.includes('"type"') ||
    payload.includes("'type'") ||
    /^type:\\s*/m.test(payload)
  ))
    return false;
  return hasRunctxToolDeclaration(payload);
}

function isAssistantOwnedBlock(node) {
  const message = node.closest("[data-message-author-role]");
  if (message) return message.getAttribute("data-message-author-role") === "assistant";

  const claudeMessage = node.closest(".font-claude-response");
  if (claudeMessage) return true;

  return true;
}

function getLatestAssistantMessage() {
  const selectors = [
    // ChatGPT
    '[data-message-author-role="assistant"]',
    // Claude
    ".font-claude-response",
    '[data-role="assistant"]',
    '[class*="segment-assistant"]',
    '[class*="chat-content-item-assistant"]',
    // Generic assistant wrappers
    '[data-message-author-role="assistant"]',
    ".message-assistant",
    '[class*="assistant-message"]',
    // Generic assistant wrappers (multiple markdown renderers)
    '[data-message-role="assistant"]',
    '[class*="assistant-message"]',
    '[class*="assistant"]',
    ".markdown-body",
  ];

  const messages = selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
  return messages.at(-1) || null;
}

// Extract text from a Monaco-rendered code block.

// Extract text from a CodeMirror 6 code block.
// CodeMirror renders each line as a <div class="cm-line"> inside .cm-content.
function extractCodeMirrorText(container) {
  const lineNodes = container.querySelectorAll(".cm-line");
  if (!lineNodes.length) return "";
  return Array.from(lineNodes)
    .map((line) => (line.innerText || line.textContent || "").replace(/\u00a0/g, " "))
    .join("\n");
}

function getCodeBlocks() {
  // Always scan the WHOLE document. Relying on an "assistant message" root is
  // fragile: site wrappers change, and a wrong root hides new payloads
  // (exactly the "only first payload copied" bug). Document-wide scan + hash
  // dedup downstream is safe because we only pick blocks that declare a
  // runctx tool.
  const blocks = [];

  const seen = new Set();
  const pushBlock = (text) => {
    if (!text) return;
    if (seen.has(text)) return;
    seen.add(text);
    blocks.push(text);
  };

  // Standard markdown code blocks (ChatGPT / Claude / Gemini)
  // Skip a <pre> that already contains a <code> — the inner <code> node is
  // pushed separately below, so we avoid double-pushing the same block.
  Array.from(document.querySelectorAll("pre code, pre"))
    .filter((node) => isAssistantOwnedBlock(node))
    .filter((node) => !(node.tagName === "PRE" && node.querySelector("code")))
    .forEach((node) => {
      pushBlock(
        window.__RUNCTX__.HashUtils.cleanCodeBlock(node.innerText || node.textContent || "")
      );
    });

  // CodeMirror-rendered code blocks
  Array.from(document.querySelectorAll(".cm-editor")).forEach((node) => {
    pushBlock(window.__RUNCTX__.HashUtils.cleanCodeBlock(extractCodeMirrorText(node)));
  });

  // Streamdown-rendered code blocks: <div data-streamdown="code-block-body">
  // wraps a <pre><code> where each line is a <span class="block">.
  // innerText of the <code> preserves the newlines, so we can read it directly.
  Array.from(document.querySelectorAll('[data-streamdown="code-block-body"]')).forEach((node) => {
    const code = node.querySelector("pre code") || node.querySelector("code") || node;
    pushBlock(window.__RUNCTX__.HashUtils.cleanCodeBlock(code.innerText || ""));
  });

  // Shiki-rendered code blocks: <pre class="shiki shiki-code-block"><code>.
  // Each line is a <span class="line">. Reconstruct text from the line spans
  // to be robust against innerText quirks with pre-wrap + shiki markup.
  Array.from(document.querySelectorAll("pre.shiki-code-block, pre.shiki")).forEach((node) => {
    const code = node.querySelector("code") || node;
    const lineNodes = code.querySelectorAll("span.line");
    let text;
    if (lineNodes.length) {
      text = Array.from(lineNodes)
        .map((line) => (line.innerText || line.textContent || "").replace(/\u00a0/g, " "))
        .join("\n");
    } else {
      text = code.innerText || code.textContent || "";
    }
    pushBlock(window.__RUNCTX__.HashUtils.cleanCodeBlock(text));
  });

  return blocks;
}

function getPayloadId(payload) {
  try {
    const parsed = JSON.parse(payload);
    if (parsed.id) {
      return String(parsed.id);
    }
  } catch {}
  return null;
}

function isParseableJson(text) {
  if (!text) return false;
  const trimmed = text.trim();
  // Only require JSON validity for JSON-shaped payloads (start with "{").
  // YAML payloads start with a key, so they are left to looksLikeRunctxPayload.
  if (!trimmed.startsWith("{")) return false;
  try {
    JSON.parse(trimmed);
    return true;
  } catch {
    return false;
  }
}

function getLastPayloadBlock() {
  const blocks = getCodeBlocks();

  // Collect every block that is a valid runctx payload, together with its id.
  // Arena-style sites render TWO side-by-side model answers, and the DOM order
  // of those columns is not stable (lazy render / portals). Picking "the last
  // block in DOM" then returns the wrong (older) payload and the watcher goes
  // silent because its hash already matched. Instead pick the payload with the
  // HIGHEST id — ids are timestamps, so the largest one is always the newest.
  let best = null;
  let bestId = -Infinity;
  let fallback = null;

  for (const block of blocks) {
    if (!looksLikeRunctxPayload(block)) continue;

    const trimmed = block.trim();
    // If it looks like JSON (starts with "{"), it MUST parse — this rejects
    // echo fragments like `{...}\n\n[ENV: shell=Zsh]` that are conversation
    // text, not a fresh runctx payload.
    if (trimmed.startsWith("{") && !isParseableJson(trimmed)) continue;

    if (!fallback) fallback = block;

    const id = getPayloadId(block);
    const numericId = id !== null && /^\d+$/.test(id) ? Number(id) : null;

    if (numericId !== null) {
      if (numericId > bestId) {
        bestId = numericId;
        best = block;
      }
    }
  }

  return best || fallback;
}

window.__RUNCTX__.PayloadDetector = {
  hasRunctxToolDeclaration,
  looksLikeRunctxPayload,
  isAssistantOwnedBlock,
  getLatestAssistantMessage,
  getCodeBlocks,
  getPayloadId,
  getLastPayloadBlock,

  // Feature modules call this at load time to register their payload type
  // so detection picks it up.
  registerSpecialType(type) {
    if (typeof type === "string" && type && !RUNCTX_SPECIAL_TYPES.includes(type)) {
      RUNCTX_SPECIAL_TYPES.push(type);
    }
  },
};
