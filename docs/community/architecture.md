# Architecture

Community edition. Three parts cooperate: the **content script** (in the AI
tab), the **watcher** (Python, `watchctx`), and the **HTTP bridge** (part of the
watcher).

```
AI tab (Chrome content script)
  ├── payload-detector.js     scan code blocks → find the newest runctx payload
  ├── payload-stability.js    wait until the payload stops streaming
  ├── payload-watcher.js      dedup → clipboard write → toast
  ├── result-watcher.js       poll bridge → inject result → auto-send
  └── adapters/*.js           per-site DOM glue (getChatInput, getSendButton, …)
        │
        │ clipboard (payload out, result in)
        ▼
watchctx (Python)
  ├── clipboard poll/event
  ├── payload.py              parse JSON / YAML payload
  ├── dispatcher.py           tool → handler
  ├── handlers.py             shell / read / replace / write
  ├── subruns.py              registry for running shell sub-processes
  └── bridge.py               HTTP bridge: /result, /log, /rpc, /state, /subruns
        │
        ▼
  .state/                     results, log, sub-run registry
```

---

## Payload → result loop

1. The AI emits a JSON payload inside a fenced code block (tool `shell`,
   `read`, `replace`, `write`).
2. `payload-detector.js` scans the document for code blocks that declare one of
   those tools and picks the one with the **highest numeric `id`** (ids are
   millisecond timestamps → the largest is the newest).
3. `payload-stability.js` waits for the payload to stop changing before it is
   considered final.
4. `payload-watcher.js` checks the per-tab **processed queue** (last 100 keys,
   persisted in `chrome.storage.local.processedPayloadKeys_<tabId>`) and, if the
   payload is new, writes it to the clipboard.
5. `watchctx` reads the clipboard, parses the payload, dispatches it, and writes
   a JSON result into `.state/`.
6. `result-watcher.js` polls the bridge (`GET /result`), injects the result into
   the composer, and clicks the adapter's send button.

The loop continues until the Automation toggle is OFF.

---

## Content script

Runs on the supported AI hosts listed in `runctx-extension/manifest.json`. In
the **isolated world** — page scripts cannot see `window.__RUNCTX__`.

- `content-marker.js` is the first entry of `content_scripts[0].js` and sets
  `window.__RUNCTX_IS_CONTENT_SCRIPT__ = true` before anything else runs.
- `adapters/index.js` exposes `window.__RUNCTX__.AdapterRegistry` — picks the
  adapter by hostname, finds the composer, pastes text, clicks send.
- `services/*.js` handle detection, stability, the watcher loop, and result
  injection.
- `transports/clipboard.js` writes the payload; `transports/http-bridge.js`
  talks to the local bridge through the background service worker.

## Background service worker

`runctx-extension/background.js`:

- Proxies bridge HTTP calls (`RUNCTX_BRIDGE_*` messages) so content scripts and
  the popup never fetch localhost directly.
- Probes ports 8765–8785 to find the live bridge (`resolveBridgePort`).
- Cleans up per-tab storage on `chrome.tabs.onRemoved`.
- Opens the side panel on action click.

## Backend

- `runctx/dispatcher.py` maps each tool to a handler in a dict
  (`_TOOL_HANDLERS`) — no if/else chain.
- `runctx/handlers.py` implements `shell`, `read`, `replace`, `write`.
- `runctx/bridge.py` is a threaded HTTP server on `127.0.0.1`.
- `runctx/subruns.py` tracks running `shell` sub-processes so they can be listed
  and killed, and so no orphans survive `watchctx` shutdown.

---

## Storage

| Location | What |
|---|---|
| `chrome.storage.local.enabled` | Automation toggle |
| `chrome.storage.local.pinnedTabId` | Optional: restrict automation to one tab |
| `chrome.storage.local.processedPayloadKeys_<tabId>` | Per-tab payload dedup queue |
| `chrome.storage.local.envSettings` | Environment settings (shell, stack, package manager) |
| `chrome.storage.local.speedMode` | Automation speed |
| `.state/` (repo) | Bridge result, log, sub-run registry |
