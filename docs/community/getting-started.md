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
| OS | Windows 10+, macOS 11+, Linux (Ubuntu 20.04+ / equivalent), WSL |
| Python | 3.8 or above (3.11+ recommended) |
| Browser | Chrome 100+ or Edge 100+ (Manifest V3) |

No GPU, no Docker, no admin rights needed.

---

## Setup — step by step

Follow these in order. Each step has something you can verify before moving on.

### Step 1 — Clone

```bash
git clone https://github.com/jsonnguyen19/sonsery-flow-community.git
cd sonsery-flow-community
```

### Step 2 — Run setup

```bash
pnpm setup
```

> No `pnpm`? Install it once: `npm install -g pnpm`. Or run the script
> directly: `python3 scripts/setup.py`.

This creates `venv/`, installs runtime deps, and writes three wrappers at the
repo root: **`run`**, **`sync`**, **`run-mobile`**.

### Step 3 — Test it runs

```bash
./run
```

You should see the clipboard watcher start and the HTTP bridge announce a port
in the `8765–8785` range. **Leave this terminal running.**

On Windows (cmd/PowerShell) use `run.bat` instead:

```powershell
.\run.bat
```

### Step 4 — Configure the alias (WSL first)

Setup does **NOT** write aliases for you — add them yourself so you can type
`watchctx` from any directory.

**WSL / Linux / macOS (bash / zsh)** — add to `~/.bashrc` or `~/.zshrc`,
replacing `/path/to/sonsery-flow-community` with your actual clone path:

```bash
alias watchctx='/path/to/sonsery-flow-community/run'
alias watchctx-sync='/path/to/sonsery-flow-community/sync'
```

<details>
<summary><b>Other shells (Windows PowerShell, Git Bash) — click to expand</b></summary>

**Windows PowerShell** — add to `$PROFILE`:

```powershell
function watchctx      { & "C:\path\to\sonsery-flow-community\run.bat" @args }
function watchctx-sync { & "C:\path\to\sonsery-flow-community\sync.bat" @args }
```

**Git Bash** — same as WSL:

```bash
alias watchctx='/c/path/to/sonsery-flow-community/run'
alias watchctx-sync='/c/path/to/sonsery-flow-community/sync'
```

</details>

### Step 5 — Reload your terminal

Either open a new terminal or source the config file:

```bash
source ~/.zshrc      # zsh
. ~/.bashrc          # bash
```

### Step 6 — Verify the terminal

Run:

```bash
watchctx
```

Same output as Step 3 = **terminal setup done**.

### Step 7 — Load the Chrome extension

```bash
pnpm about
```

Copy the **Extension path**. Then:

1. Open `chrome://extensions/` (or `edge://extensions/`), enable **Developer mode**.
2. **Load unpacked** → paste the path
   (on WSL: paste the **Windows UNC path** — `\\wsl.localhost\<Distro>\home\...\runctx-extension` — into the Explorer address bar and press Enter first).
3. **Pin** the extension and **reload** it once.
4. Shortcut: `Ctrl+Shift+Space`.

### Step 8 — Test with DeepSeek

1. Open `chat.deepseek.com`.
2. Click the pinned Sonsery Flow icon → side panel opens.
3. Flip **Automation** toggle **ON**.
4. **Copy this ready-made payload** and send it in the chat:

```json
{ "id": 1791016717000, "tool": "shell", "mode": "sequential", "commands": ["pwd"] }
```

> Bump the `id` to any newer millisecond timestamp (e.g. `Date.now()`) if the
> extension ever reports the payload as already processed.

5. Watch the loop: payload copied → `watchctx` runs it → result (your current
   working directory) pasted back.

If you see the result come back, **setup is complete**. 🎉

---

## Bonus — a dedicated background Chrome for coding

**Strongly recommended for daily use.** Two reasons:

1. **Chrome throttles background tabs.** By default Chrome slows timers,
   freezes inactive tabs, and sleeps background windows. The automation loop
   needs the AI tab to stay *awake* — when it loses focus, the loop can stall.
2. **The loop only runs while its Chrome instance is active.** If you reuse
   your everyday Chrome and then switch away to do other work, the AI tab is
   deprioritised and the loop pauses. Isolating the agent in its **own Chrome
   profile, launched in the background**, lets you keep using your main Chrome
   normally while the agent keeps working.

Launch Chrome with a separate profile and the flags below so the loop keeps
running when minimized or unfocused.

```bash
# macOS example
open -na "Google Chrome" --args \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome Agent" \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  --intensive-wake-up-throttling-policy=disabled
```

See the main README "Bonus — a dedicated background Chrome for coding" section
for Windows (PowerShell) and Linux (`.desktop`) variants.

> **Tip:** Install the extension into this dedicated profile once. Keep the
> window minimized — the loop keeps running.

---

## Usage — driving the loop day to day

Setup is done once. This section is what you actually do **every session**.

### 1. Open the AI site and enable automation

1. In your browser (Chrome or Edge — one of the AI sites the Community build
   supports: **ChatGPT, Claude, Gemini, DeepSeek**), open the chat tab you want
   to work with.
2. Click the pinned Sonsery Flow icon → the side panel opens on the **Flow** tab.
3. **Pin this tab** so automation is scoped to it (recommended when you keep
   other AI tabs open).
4. Flip the **Automation** toggle **ON**.

### 2. Inject the instructions into the chat

Click **Inject context** in the Flow tab. This drops the `agentctx` prompt into
 the chat composer — it is the contract that teaches the AI the payload protocol
(`id`, `tool`, `shell` / `read` / `replace` / `write`, how to reply). Without
this step the AI has no idea what a "payload" is.

- **DeepSeek** — inject directly in a normal chat. DeepSeek keeps the context
  reliably across turns, so a fresh tab is fine.
- **ChatGPT** — create a dedicated **Project** (left sidebar → New project) and
  paste the injected instructions into the Project's instructions field **once**.
  Every chat inside that project then starts with the protocol already loaded,
  and you avoid re-injecting on every new chat.

### 3. Start the session with a task

After the instructions are in place, **move to a new line** and type:

```
Give me a payload to do this task: <describe the task here>
```

e.g. `Give me a payload to do this task: read README.md and list the setup steps`.

Two things happen at once:

- The AI answers with a first payload instead of a generic greeting.
- **The session is named after your task line** — no more renaming chats by
  hand in the sidebar.

Send it. The extension detects the payload, copies it, `watchctx` runs it, and
 the result is pasted back. From here just keep chatting — ask for the next task
when the result comes back.

### 4. Pick the right AI for the job

Not every model plays equally well with the tool protocol:

| AI | Experience |
|---|---|
| **Claude** | Best overall — follows the payload format, stays on-rails on multi-step tasks. |
| **DeepSeek** | Very close to Claude — fast, cheap, reliable. |
| **Gemini** | Works, but less smooth — sometimes drifts from the format and needs re-prompting. |
| **ChatGPT** | Same caveat as Gemini — usable, but the loop is not as fluid. |

If you want the tool to feel invisible, prefer **Claude** or **DeepSeek**.

---

## Manual mode

Don't want the loop running on its own? Leave Automation **OFF** and use the
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
