# Sonsery Flow Community - AI Workflow Automation

A tool that automates the workflow between AI Chat (ChatGPT, Claude, Gemini, DeepSeek) and the terminal. Community edition — MIT, open source.

## How it works

1. Copy the payload from AI Chat to the clipboard
2. `watchctx` automatically detects it and executes the command
3. The result is copied back to the clipboard to paste into AI Chat

## Setup (end-user)

```bash
python3 scripts/setup.py
```

at the project root. Then:

```bash
./run             # Run watchctx (clipboard watcher + HTTP bridge)
./sync            # Sync prompts into the extension
```

### Aliases (optional — user configures themselves)

Setup does **NOT** write aliases into the rc file automatically. You add the
alias/function to your shell config yourself if you want to type `watchctx` from
any directory.

**Linux/macOS/WSL (bash/zsh)** — add to `~/.bashrc` or `~/.zshrc`:

```bash
alias watchctx='/path/to/sonsery-flow/run'
alias watchctx-sync='/path/to/sonsery-flow/sync'
```

Or as a function (more flexible, no hard-coded wrapper):

```bash
watchctx()      { python3 '/path/to/sonsery-flow/watchctx.py' "$@"; }
watchctx-sync() { python3 '/path/to/sonsery-flow/sync-prompts.py' "$@"; }
```

**Windows (PowerShell)** — add to `$PROFILE`:

```powershell
function watchctx      { & "C:\path\to\sonsery-flow\run.bat" @args }
function watchctx-sync { & "C:\path\to\sonsery-flow\sync.bat" @args }
```

`profile.ps1.example`, `config.fish.example`, `cmdrc.example.bat`).


> After adding the alias, **open a new terminal** (or `source ~/.zshrc` /
> `. ~/.bashrc`) to reload the config.

## Tool info

```bash
pnpm about                     # or: python3 scripts/about.py
```

Prints version, project root, extension path for Load unpacked, HTTP
bridge ports, and a list of available commands.

## Setup (dev)

```bash
pnpm install       # Install dev deps (husky pre-commit hook auto-installs via "prepare")
pnpm setup:dev     # Create .venv-test/, install requirements-dev.txt
pnpm check         # lint + format check + typecheck + test
```

End-users only need `pnpm setup` (or `python3 scripts/setup.py`) as in the section
above. The pre-commit hook (husky + lint-staged) automatically runs ESLint + Prettier for JS/CSS/HTML files
under `runctx-extension/`, and ruff check + format for staged `.py` files.

See [`scripts/README.md`](scripts/README.md) for details.

## Usage

```bash
./run             # Run clipboard watcher + HTTP bridge
./sync            # Sync prompts into the extension
```

## Chrome Extension

Install the extension from the `runctx-extension/` folder:
- Open `chrome://extensions/`
- Enable Developer mode
- Load unpacked → select `runctx-extension/`
- Shortcut: `Ctrl+Shift+Space`

### Bonus: keep Chrome running in the background (recommended)

By default Chrome throttles timers, freezes tabs, and sleeps background windows —
this can pause the automation loop when the AI tab is not focused. Launch Chrome
with the flags below so the loop keeps running even when you minimize or switch
away.

**Flags used (all Chrome/Edge-compatible):**

| Flag | Purpose |
|---|---|
| `--user-data-dir="..."` | Use a separate profile so it doesn't conflict with your main Chrome |
| `--disable-background-timer-throttling` | Don't slow down timers in background tabs |
| `--disable-backgrounding-occluded-windows` | Don't deprioritize covered/occluded windows |
| `--disable-renderer-backgrounding` | Don't lower renderer priority in the background |
| `--intensive-wake-up-throttling-policy=disabled` | Disable the aggressive wake-up throttling policy |

#### Windows (PowerShell) — create a dedicated shortcut

Run in PowerShell (adjust `$ShortcutPath` to wherever you want the shortcut):

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Chrome Agent.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

# Flags to stop Chrome from freezing / sleeping background tabs
$Shortcut.TargetPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$Shortcut.Arguments = '--user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data Agent" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --intensive-wake-up-throttling-policy=disabled'

$Shortcut.Save()
Write-Host "Chrome Agent shortcut created successfully!" -ForegroundColor Green
```

Then launch Chrome from the shortcut and load the extension in that profile.

#### macOS — launch from Terminal (or wrap in an app/alias)

```bash
open -na "Google Chrome" --args \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome Agent" \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  --intensive-wake-up-throttling-policy=disabled
```

#### Linux — create a `.desktop` launcher

Save as `~/.local/share/applications/chrome-agent.desktop`:

```ini
[Desktop Entry]
Name=Chrome Agent
Exec=/usr/bin/google-chrome --user-data-dir=%h/.config/google-chrome-agent --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --intensive-wake-up-throttling-policy=disabled
Type=Application
Terminal=false
```

> **Note:** These flags apply to Chrome. For Edge, replace the executable path
> (`chrome.exe` → `msedge.exe`, `Google Chrome` → `Microsoft Edge`, etc.) — the
> flag names are identical.

> **Tip:** Using a separate `--user-data-dir` keeps your agent profile isolated
> from your daily browser, so extension reloads and login state for the AI sites
> stay separate.

## Structure

- `watchctx.py` — entrypoint (facade): clipboard watcher + HTTP bridge
- `runctx_core.py` — entrypoint (facade): payload processing
- `runctx/` — main package
- `runctx-extension/` — Chrome extension
- `scripts/` — setup scripts (see `scripts/README.md`)
- `prompts/` — prompt templates
- `tests/python/` — pytest test suite

## Requirements

- Python 3.8+
- Chrome/Edge
