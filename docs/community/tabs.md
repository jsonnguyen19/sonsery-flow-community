# Side-panel tabs

The Community side panel has **4 tabs**: Flow, Stats, History, Settings.

When the panel is narrow, tabs that don't fit move into a **⋯ overflow menu**
(`popup/tabs.js` recomputes this on every resize).

---

## Flow (`flow`)

The main tab.

- **Automation toggle** — writes `enabled` to storage and tells the content
  script (`RUNCTX_SET_STATE`). Badge shows ON/OFF.
- **Watch status** — `watchctx @ <pwd>` when the bridge is up, `no watchctx`
  otherwise. Polled every second.
- **Pin this tab** — restricts automation to the current tab
  (`pinnedTabId`). Cleared when the tab closes.
- **Manual controls** — Copy / Paste / Send / Clear (one-shot actions that work
  regardless of the Automation toggle).
- **Inject context** — dropdown + button. Injects the `agentctx` prompt with the
  `<unix_ms_now>` ID protocol applied (`INIT_ID = <unix_ms>`).
- **Toasts toggle** — show/hide in-page toasts.
- **Play-result-sound toggle**.
- **Reset session tokens** — clears the session token counters.

Implementation: `popup.html` + `popup.js` + `popup/actions*.js` +
`popup/actions-manual.js` + `popup/actions-inject.js` + `popup/helpers.js`.

---

## Stats (`stats`)

Four counters: `sessionTokens`, `inputTokens`, `outputTokens`, `opCount`. Plus a
reset button.

Implementation: `popup/tokens.js` + `popup/stats.css`.

---

## History (`history`)

Reads `.state/payload_history.json` through the bridge RPC
(`get_history` / `get_history_detail` / `clear_history` / `set_history_cap`) via
`window.__RUNCTX__.RpcClient`.

- List of the last N payloads (default 50 per page; cap 20–1000).
- Click a row to expand an inline detail drawer.
- Editable cap + clear button.

Implementation: `popup/history.js` + `popup/history.css`.

---

## Settings (`settings`)

- **Environment** — `shell`, `techStack`, `packageManager`, `maxResponseLength`.
  Non-auto values are folded into a `[ENV: …]` block injected with prompts.
- **Theme** — system / dark / light.
- **Automation Speed** — slow / normal / fast / veryFast, plus a details modal
  that shows the per-mode delay.
- **Payload queue** — view / search / reset the per-tab dedup queue
  (`processedPayloadKeys_<tabId>`).

Implementation: `popup/settings.js` + `popup/speed.js`.

---

## Cross-tab behaviour

- `popup.js` calls `render()` every second to refresh the badge, pin button, and
  watch status.
- The Stats tab refreshes its counters every 5 seconds while it is active.
- `watchctx` exposes its log tail over the bridge at `GET /log?since=&limit=`;
  the Community panel itself is a 4-tab UI (Flow, Stats, History, Settings).
