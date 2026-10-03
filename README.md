# Sonsery Flow Community - AI Workflow Automation

[![CI](https://github.com/jsonnguyen19/sonsery-flow-community/actions/workflows/ci.yml/badge.svg)](https://github.com/jsonnguyen19/sonsery-flow-community/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Manifest V3](https://img.shields.io/badge/Chrome-Manifest%20V3-4285F4?logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/develop/migrate/what-is-mv3)

![Sonsery Flow — Turn free web AI into your CLI agent](docs/assets/thumbnail.png)

> **Sonsery Flow** — use free web AI (ChatGPT, Claude, Gemini, DeepSeek, and more)
> as a coding agent, right inside your terminal. No API keys, no subscriptions,
> no token quotas. Copy a payload in the AI chat → the tool runs it on your
> machine → the result is pasted back. Automation loop, end to end.

A tool that automates the workflow between AI Chat (ChatGPT, Claude, Gemini, DeepSeek) and the terminal. Community edition — MIT, open source.

## How it works

1. Copy the payload from AI Chat to the clipboard
2. `watchctx` automatically detects it and executes the command
3. The result is copied back to the clipboard to paste into AI Chat

## Quick start

> **Using the tool?** You only need the two steps below. Ignore anything about
> `pnpm setup:dev` — that is for contributors.

```bash
python3 scripts/setup.py

# 2. Run
./run             # clipboard watcher + HTTP bridge
./sync            # sync prompts into the extension
```

That's it for the backend. Next, install the browser extension.

## Browser extension

The Chrome/Edge extension lives in `runctx-extension/`. The Firefox build is
produced by `pnpm ext:firefox` into `runctx-extension-firefox/`. To find the
Chrome extension's exact path (and get it in a form Windows/WSL can paste
directly), run:

```bash
pnpm about                     # or: python3 scripts/about.py
./run --about                  # or ./run -a
```

This prints the extension path, HTTP bridge ports, and available commands.

### Fields worth knowing

| Field | Why it matters |
|---|---|
| `Extension path` (WSL UNC) | **The key one.** On WSL, `about` prints the Windows UNC form — `\\wsl.localhost\<Distro>\home\...\runctx-extension`. Copy this **straight into the Explorer address bar** and hit Enter, then use it as the folder for `Load unpacked`. No manual path translation needed. |
| `Extension path` (Linux) | The raw POSIX path, kept for reference. Ignore it on Windows — use the UNC path above. |
| `HTTP bridge ports` | The port range the clipboard watcher + bridge listen on. The bridge scans **8765 through 8785**, plus **8899** (mobile remote). Useful when debugging or when a port is already taken. |
| `Project root` / `Platform` / `Python` | Environment info — the first thing to include in a bug report. |

### Install — Chrome / Edge

1. Run `pnpm about` and copy the **WSL UNC path** (Windows) or the plain path
   (Linux/macOS).
2. Open `chrome://extensions/` (or `edge://extensions/`) and enable **Developer mode**.
3. Click **Load unpacked** → paste the path
   (on WSL, paste into the Explorer address bar and press Enter first) → select.
4. Shortcut: `Ctrl+Shift+Space`.

### Install — Firefox

Firefox needs the manifest to be named exactly `manifest.json`, so a dedicated
build folder is produced:

```bash
pnpm ext:firefox        # produces runctx-extension-firefox/
```

Then:

1. Open `about:debugging#/runtime/this-firefox`.
2. **Load Temporary Add-on** → pick `runctx-extension-firefox/manifest.json`.

See [`docs/dev/firefox.md`](docs/dev/firefox.md) for the throttling tweaks (about:config)
that make Firefox behave like Chrome, and how to move the sidebar to the right.

### Optional: keep Chrome running in the background (recommended)

By default Chrome throttles timers, freezes tabs, and sleeps background windows —
this can pause the automation loop when the AI tab is not focused. Launch Chrome
with the flags below so the loop keeps running even when you minimize or switch
away.

| Flag | Purpose |
|---|---|
| `--user-data-dir="..."` | Use a separate profile so it doesn't conflict with your main Chrome |
| `--disable-background-timer-throttling` | Don't slow down timers in background tabs |
| `--disable-backgrounding-occluded-windows` | Don't deprioritize covered/occluded windows |
| `--disable-renderer-backgrounding` | Don't lower renderer priority in the background |
| `--intensive-wake-up-throttling-policy=disabled` | Disable the aggressive wake-up throttling policy |

**Windows (PowerShell)** — create a dedicated shortcut:

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Chrome Agent.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

$Shortcut.TargetPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$Shortcut.Arguments = '--user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data Agent" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --intensive-wake-up-throttling-policy=disabled'

$Shortcut.Save()
```

**macOS** — launch from Terminal:

```bash
open -na "Google Chrome" --args \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome Agent" \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  --intensive-wake-up-throttling-policy=disabled
```

**Linux** — save as `~/.local/share/applications/chrome-agent.desktop`:

```ini
[Desktop Entry]
Name=Chrome Agent
Exec=/usr/bin/google-chrome --user-data-dir=%h/.config/google-chrome-agent --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --intensive-wake-up-throttling-policy=disabled
Type=Application
Terminal=false
```

> **Note:** For Edge, replace the executable path (`chrome.exe` → `msedge.exe`,
> `Google Chrome` → `Microsoft Edge`) — the flag names are identical.

> **Tip:** A separate `--user-data-dir` keeps the agent profile isolated from your
> daily browser, so extension reloads and AI-site login state stay separate.

## Pro & Community

The repo you are reading is the **Pro build** — it ships with all Pro features.
The **Community (MIT)** build is produced at build time by
`scripts/split-community.sh` into a separate repo; it contains no Pro code in
any form.

| | Community (MIT) | Pro ($39 one-time) |
|---|---|---|
| Core automation (shell/read/replace/write) | ✅ | ✅ |
| Adapters | chatgpt + claude + gemini + deepseek + fallback | all 13 |
| Tabs | Flow, Stats (overview), History, Settings | + Project, Terminal, Skills |
| License key | not needed | required (max 3 machines) |
| Multi-agent switch, , @mention, mobile remote | ❌ | ✅ |
| Firefox build | ❌ | ✅ |

For the full split architecture see [`docs/split/0-overview.md`](docs/split/0-overview.md).

### License (Pro)

The Pro build has a runtime **license gate**: automation is paused when the
stored key is `invalid` / `unlicensed` / `stale`. Enter / manage the key in the
**Settings tab → License**. Storage key = `license` in `chrome.storage.local`.

> The current build runs the license subsystem in **simulated mode**
> (`SIMULATE = true` in `popup/license.js`) — no backend calls yet. Real API
> integration (LemonSqueezy) is pending; see
> [`docs/split/5-checklist.md`](docs/split/5-checklist.md) §12.

## Aliases (optional)

Setup does **NOT** write aliases automatically. Add these yourself if you want to
type `watchctx` from any directory.

**Linux/macOS/WSL (bash/zsh)** — add to `~/.bashrc` or `~/.zshrc`:

```bash
alias watchctx='/path/to/sonsery-flow/run'
alias watchctx-sync='/path/to/sonsery-flow/sync'
```

**Windows (PowerShell)** — add to `$PROFILE`:

```powershell
function watchctx      { & "C:\path\to\sonsery-flow\run.bat" @args }
function watchctx-sync { & "C:\path\to\sonsery-flow\sync.bat" @args }
```

> After adding the alias, **open a new terminal** (or `source ~/.zshrc` /
> `. ~/.bashrc`) to reload the config.

## Requirements

- Python 3.8+
- Chrome/Edge (or Firefox for the Pro Firefox build)

## Links

- **Website / Landing page** — <https://flow.sonsery.online/>
- **Community repo** — <https://github.com/jsonnguyen19/sonsery-flow-community>
- **Author portfolio** — <https://jasonnguyen.website/>
- **LinkedIn** — <https://www.linkedin.com/in/son-nguyen-650628344/>
- **Contact** — hongsonit10@gmail.com
- **Discord** — coming soon

## Contributing

Contributor / dev setup (dev venv, lint, format, typecheck, tests) lives in
[`docs/dev/setup.md`](docs/dev/setup.md). End-users never need it.

Repo layout:

- `watchctx.py` — entrypoint: clipboard watcher + HTTP bridge
- `runctx_core.py` — entrypoint: payload processing
- `runctx/` — main package
- `runctx-extension/` — Chrome/Edge extension (Pro build)
- `runctx-extension-firefox/` — Firefox build output (`pnpm ext:firefox`)
- `mobile/` — mobile remote server (Pro)
- `scripts/` — setup scripts (see [`scripts/README.md`](scripts/README.md))
- `scripts/split-community.sh` / `scripts/sync-community.sh` — Community repo
  build + sync (see [`docs/split/3-workflow.md`](docs/split/3-workflow.md))
- `prompts/` — prompt templates
- `tests/python/` — pytest test suite

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide.
