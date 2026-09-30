#!/usr/bin/env python3
"""
End-user setup script for Sonsery Flow.

Installs:
- venv/ (virtual environment)
- Runtime dependencies (from requirements.txt)
- Prints instructions to configure aliases `watchctx` / `watchctx-sync` /
- Instructions to install the Chrome extension

Devs should use `pnpm setup:dev` (runs `scripts/setup-dev.sh`) to get the full
tooling (pytest, ruff, basedpyright).

Run:
    python3 scripts/setup.py
"""

import os
import platform
import subprocess
import sys
import venv
from pathlib import Path


class Setup:
    def __init__(self):
        # scripts/setup.py -> project root = parent of scripts/
        self.project_root = Path(__file__).resolve().parent.parent
        self.venv_dir = self.project_root / "venv"
        self.venv_bin = self.venv_dir / ("Scripts" if platform.system() == "Windows" else "bin")
        self.pip = self.venv_bin / ("pip.exe" if platform.system() == "Windows" else "pip")

    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")

    def run_cmd(self, cmd, cwd=None, env=None):
        """Run a command and return its output."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd or self.project_root,
                env=env or os.environ,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {cmd}", "ERROR")
            self.log(f"Output: {e.stdout}", "ERROR")
            self.log(f"Error: {e.stderr}", "ERROR")
            raise

    def check_python(self) -> bool:
        """Check that Python 3.8+ is available (try python3, then python)."""
        self.log("Checking Python...")
        for candidate in ("python3", "python"):
            try:
                output = subprocess.check_output([candidate, "--version"], text=True)
            except Exception:
                continue

            version = output.strip().split()[1]
            try:
                major, minor = map(int, version.split(".")[:2])
            except ValueError:
                continue

            if major < 3 or (major == 3 and minor < 8):
                self.log(f"Python 3.8+ required, you are running {version}", "ERROR")
                return False

            self.log(f"Python {version} OK ({candidate})")
            return True

        self.log("Python not found. Install Python 3.8+", "ERROR")
        return False

    def create_venv(self) -> bool:
        """Create the virtual environment if it does not exist yet."""
        if self.venv_dir.exists():
            self.log(f"Virtual env already exists at {self.venv_dir}")
            return True

        self.log("Creating virtual environment...")
        try:
            venv.create(self.venv_dir, with_pip=True)
            self.log(f"Virtual env created at {self.venv_dir}")
            return True
        except Exception as e:
            self.log(f"Failed to create virtual env: {e}", "ERROR")
            return False

    def install_pip_deps(self) -> bool:
        """Install runtime deps from requirements.txt."""
        self.log("Installing Python dependencies...")

        req_file = self.project_root / "requirements.txt"
        if not req_file.exists():
            self.log(f"Cannot find {req_file}", "ERROR")
            return False

        self.run_cmd(f'"{self.pip}" install -r "{req_file}"')
        self.log("Dependencies installed")
        return True

    def setup_hooks(self) -> bool:

        is_windows = platform.system() == "Windows"

        if is_windows:
            run_script = self.project_root / "run.bat"
            run_content = (
                "@echo off\n"
                "setlocal\n"
                "if not defined WATCHCTX_NOPROMPT (\n"
                '  set "WATCHCTX_NOPROMPT=1"\n'
                '  <nul call "%~f0" %*\n'
                "  exit /b\n"
                ")\n"
                'set "ROOT=%~dp0"\n'
                'set "VENV=%ROOT%venv"\n'
                'set "PY=%VENV%\\Scripts\\python.exe"\n'
                'set "STAMP=%VENV%\\requirements.stamp"\n'
                "set PYTHONUTF8=1\n"
                "\n"
                'if exist "%PY%" goto check_deps\n'
                "\n"
                "echo [watchctx] First run - creating virtual environment...\n"
                "where py >nul 2>nul\n"
                'if not errorlevel 1 (py -3 -m venv "%VENV%") else (python -m venv "%VENV%")\n'
                'if not exist "%PY%" (\n'
                "  echo [watchctx] ERROR: cannot create venv. Install Python 3.8 or newer "
                "from python.org and tick Add Python to PATH.\n"
                "  exit /b 1\n"
                ")\n"
                "\n"
                ":check_deps\n"
                'fc /b "%ROOT%requirements.txt" "%STAMP%" >nul 2>nul && goto run\n'
                "\n"
                "echo [watchctx] Installing dependencies...\n"
                '"%PY%" -m pip install -q -r "%ROOT%requirements.txt"\n'
                "if errorlevel 1 (\n"
                "  echo [watchctx] ERROR: pip install failed.\n"
                "  exit /b 1\n"
                ")\n"
                'copy /y "%ROOT%requirements.txt" "%STAMP%" >nul\n'
                "\n"
                ":run\n"
                '"%PY%" "%ROOT%watchctx.py" %*\n'
            )
            sync_script = self.project_root / "sync.bat"
            sync_content = (
                '@echo off\ncd /d "%~dp0"\n"venv\\Scripts\\python.exe" sync-prompts.py %*\n'
            )
        else:
            # IMPORTANT: do NOT `cd` into the project root.
            # watchctx writes `Path.cwd()` into watchctx.pwd as the base root
            # (the user's PWD). If the wrapper cd'd, tree/git/read/write would
            # always resolve back to the project root -> wrong. Instead:
            # resolve the project root via dirname $0 (does not change PWD),
            # set PYTHONPATH so runctx imports, then exec python by absolute
            # path.
            run_script = self.project_root / "run"
            run_content = (
                "#!/bin/bash\n"
                "# Do NOT cd: keep the user's PWD as the project root for watchctx.\n"
                'PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"\n'
                'export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"\n'
                'exec "$PROJECT_ROOT/venv/bin/python" "$PROJECT_ROOT/watchctx.py" "$@"\n'
            )
            sync_script = self.project_root / "sync"
            sync_content = (
                "#!/bin/bash\n"
                'PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"\n'
                'export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"\n'
                'exec "$PROJECT_ROOT/venv/bin/python" "$PROJECT_ROOT/sync-prompts.py" "$@"\n'
            )
        wrappers = (
            (run_script, run_content),
            (sync_script, sync_content),
        )
        for path, content in wrappers:
            if is_windows and path.name == "run.bat" and path.exists():
                self.log(f"  Keeping existing wrapper: {path}")
                continue
            path.write_text(content, encoding="utf-8")
            if not is_windows:
                os.chmod(path, 0o755)
            self.log(f"  Created wrapper: {path}")

        return True

    def print_alias_hint(self) -> bool:
        """Print instructions for the user to configure aliases themselves.

        Setup NEVER writes to rc files nor creates shims/pointers. The user
        picks whatever fits (an alias pointing at the wrapper, or a function
        that calls python3 directly).
        """
        self.log("")
        self.log("=" * 60)
        self.log("ALIAS CONFIGURATION (OPTIONAL)")
        self.log("=" * 60)
        self.log("Setup NEVER writes aliases to rc files. Configure them yourself")
        self.log("from any directory.")
        self.log("")

        is_windows = platform.system() == "Windows"
        root = self.project_root

        if is_windows:
            self.log("Windows (PowerShell) - add to $PROFILE:")
            self.log(f'  function watchctx      {{ & "{root}\\run.bat" @args }}')
            self.log(f'  function watchctx-sync {{ & "{root}\\sync.bat" @args }}')
            self.log("")
            self.log("Windows (cmd) - add to AutoRun or run directly inside the project:")
            self.log(f"  doskey watchctx={root}\\run.bat $*")
            self.log("")
            self.log("Or run directly inside the project:")
            self.log("  .\\run.bat")
        else:
            self.log("Linux/macOS/WSL (bash/zsh) - add to ~/.bashrc or ~/.zshrc:")
            self.log(f"  alias watchctx='{root}/run'")
            self.log(f"  alias watchctx-sync='{root}/sync'")
            self.log("")
            self.log("Or a function (more flexible, no hard-coded wrapper):")
            self.log(f"  watchctx()      {{ python3 '{root}/watchctx.py' \"$@\"; }}")
            self.log(f"  watchctx-sync() {{ python3 '{root}/sync-prompts.py' \"$@\"; }}")
            self.log("")
            self.log("Or run directly inside the project:")
            self.log("  ./run")
        self.log("")
        self.log(">> See tool info + all commands: pnpm about (or python3 scripts/about.py)")
        self.log("=" * 60)
        return True

    def setup_chrome_extension(self) -> bool:
        """Print instructions to install the Chrome extension."""
        self.log("")
        self.log("=" * 60)
        self.log("CHROME EXTENSION")
        self.log("=" * 60)
        self.log("To install the extension:")
        self.log("1. Open Chrome and go to chrome://extensions/")
        self.log("2. Enable 'Developer mode'")
        self.log("3. Click 'Load unpacked' and pick the runctx-extension/ folder")
        self.log("4. The extension appears as 'Sonsery Flow'")
        self.log(f"   Path: {self.project_root / 'runctx-extension'}")
        self.log("5. Default shortcut: Ctrl+Shift+Space")
        self.log("=" * 60)
        return True

    def run(self):
        """Run the whole setup."""
        self.log("=" * 60)
        self.log("SONSERY FLOW - SETUP (end-user)")
        self.log("=" * 60)

        if not self.check_python():
            sys.exit(1)

        if not self.create_venv():
            sys.exit(1)

        if not self.install_pip_deps():
            sys.exit(1)

        self.setup_hooks()
        self.print_alias_hint()
        self.setup_chrome_extension()

        self.log("")
        self.log("=" * 60)
        self.log("SETUP COMPLETE!")
        self.log("=" * 60)
        self.log("")
        is_windows = platform.system() == "Windows"

        self.log("Created:")
        if is_windows:
            self.log(f"  - {self.project_root}\\run.bat          # Run watchctx")
            self.log(f"  - {self.project_root}\\sync.bat         # Sync prompts")
        else:
            self.log(f"  - {self.project_root}/run          # Run watchctx")
            self.log(f"  - {self.project_root}/sync         # Sync prompts")
        self.log("")
        self.log("Try it:")
        if is_windows:
            self.log("  .\\run.bat            # Clipboard watcher + bridge (127.0.0.1:8765)")
            self.log("  .\\sync.bat           # Sync prompts into the extension")
        else:
            self.log("  ./run                 # Clipboard watcher + bridge (127.0.0.1:8765)")
            self.log("  ./sync                # Sync prompts into the extension")
        self.log("")
        self.log("See tool info + all commands: pnpm about")
        self.log("")
        self.log(
            "Dev: use `pnpm setup:dev` to install the full tooling (pytest, ruff, basedpyright)."
        )
        self.log("")


def main():
    Setup().run()


if __name__ == "__main__":
    main()
