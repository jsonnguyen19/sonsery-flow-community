# Web AI adapters

An **adapter** teaches the extension how to talk to one AI site: find the
composer, paste text, click send, detect when the site is busy.

Community ships **5 adapters**: `chatgpt`, `claude`, `gemini`, `deepseek`, and
`fallback`.

| # | Adapter | Host | Notes |
|---|---|---|---|
| 1 | `chatgpt` | chatgpt.com | Stable selectors |
| 2 | `claude` | claude.ai | Contenteditable; needs a focus click |
| 3 | `gemini` | gemini.google.com | Quill editor |
| 4 | `deepseek` | chat.deepseek.com | Has `collapseSidebar` |
| 5 | `fallback` | any other host | Only used when nothing matches |

Adding an adapter = a new file in `runctx-extension/adapters/<name>.js` + a host
entry in `manifest.json` (`host_permissions`, `content_scripts.matches`, and the
adapter file in `content_scripts[0].js`).

---

## Adapter interface

Every adapter exports the same shape (see `adapters/fallback.js`):

| Method | Purpose |
|---|---|
| `matches()` | Return `true` when the current hostname is this adapter's site |
| `getChatInput()` | Return the composer element (`textarea` or `contenteditable`) |
| `getSendButton()` | Return the send button, or `null` if not ready |
| `getBusyReason()` | Return a string when the site is busy (streaming), else `''` |
| `collapseSidebar()` | Optional; collapse the site sidebar. Return `true` if a click happened |

`AdapterRegistry` (`adapters/index.js`) picks the adapter by calling `matches()`
in order and falls back to `fallback`.

---

## Debugging an adapter

1. Open DevTools on the AI tab.
2. **Switch the console context** from the page to **"Sonsery Flow"** —
   `window.__RUNCTX__` only exists in the extension's isolated world.
3. Run checks:

   ```js
   window.__RUNCTX__.AdapterRegistry.getCurrentAdapter().matches()
   window.__RUNCTX__.AdapterRegistry.getChatInput()
   window.__RUNCTX__.AdapterRegistry.getCurrentAdapter().getSendButton()
   window.__RUNCTX__.PayloadDetector.getCodeBlocks()
   window.__RUNCTX__.PayloadDetector.getLastPayloadBlock()
   ```

4. If `getCodeBlocks()` returns nothing but code blocks are visible, the site
   renders code with something other than `<pre><code>` (e.g. Monaco,
   CodeMirror). Add a branch to `services/payload-detector.js::getCodeBlocks`
   for that renderer.

### Common gotchas

- **Monaco / CodeMirror** render each line as a `<div>` — reconstruct text from
  the line nodes and normalize `\u00a0` → space before parsing.
- **React-controlled composers** ignore a plain `element.textContent = …` —
  dispatch a real `paste` event (or use the native setter + `input` event).
- **Busy state** — some sites keep the send button enabled while streaming. Use
  `getBusyReason()` to avoid pasting mid-stream.

---

## Reload checklist when editing an adapter

- Reload the extension in `chrome://extensions/`.
- Hard-reload the AI tab (F5).
- Send 3 payloads in a row and confirm all 3 are copied (no stale-hash skip).
