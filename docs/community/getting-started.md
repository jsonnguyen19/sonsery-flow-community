# Getting started

Sonsery Flow (Community edition) bridges a web AI chat tab — ChatGPT, Claude,
Gemini, DeepSeek — with your local terminal. You chat with the AI as usual; the
AI emits a JSON **payload**; the extension detects it, copies it to the
clipboard; `watchctx` runs it on your machine and publishes the result back;
the extension pastes the result into the chat and clicks send. The loop repeats
by itself.

No API keys. No server. Everything runs locally.

---

## Requirements

| Component | Requirement |
|---|---|
| OS | Windows 10+, macOS 11+, Linux (Ubuntu 20.04+ / equivalent) |
| Python | 3.8 or above (3.11+ recommended) |
| Browser | Chrome 100+ or Edge 100+ (Manifest V3) |

No GPU, no Docker, no admin rights needed.

---

## 1. Install the backend

From the repo root:

```bash
python3 scripts/setup.py
```

This creates `venv/`, installs runtime deps, and writes two wrapper scripts at
the project root: `./run` and `./sync`.

## 2. Start the watcher

```bash
./run
```

`./run` starts the clipboard watcher and a local HTTP bridge on the first free
port in **8765–8785**. Leave it running in a terminal.

## 3. Load the extension

1. `pnpm about` (or `python3 scripts/about.py`) prints the exact
   `runctx-extension/` path — on WSL it prints a Windows UNC path you can paste
   straight into Explorer.
2. Open `chrome://extensions/` (or `edge://extensions/`), enable
   **Developer mode**.
3. **Load unpacked** → select the `runctx-extension/` folder.
4. Pin the extension and click the icon to open the side panel.
5. Shortcut: `Ctrl+Shift+Space`.

## 4. Run your first loop

1. Open an AI tab (e.g. `chatgpt.com`) and paste the `agentctx` prompt — click
   **Inject context** in the Flow tab, or copy it manually.
2. Flip the **Automation** toggle in the Flow tab ON.
3. Ask the AI to do something on your project. It replies with a JSON payload
   (a `shell` / `read` / `replace` / `write` block).
4. The extension copies it → `watchctx` runs it → the result is pasted back into
   the chat.

The loop keeps running until you flip the toggle OFF.

---

## Manual mode

Don't want the loop to run on its own? Leave Automation OFF and use the
**manual controls** in the Flow tab:

- **Copy** — grab the latest payload from the chat.
- **Paste** — paste the latest result into the chat composer.
- **Send** — click the AI's send button.
- **Clear** — clear the composer.

---

## Files at a glance

| Path | What it is |
|---|---|
| `watchctx.py` | Entrypoint: clipboard watcher + HTTP bridge |
| `runctx_core.py` | Entrypoint: payload processing |
| `runctx/` | Backend package (payload parsing, dispatch, handlers, bridge) |
| `runctx-extension/` | Chrome/Edge extension |
| `prompts/agentctx.txt` | Base prompt injected into the AI chat |
| `tests/` | pytest suite |
