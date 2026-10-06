#!/usr/bin/env python3
"""
About script for Sonsery Flow.

Prints basic tool info so users get up to speed quickly:
- Name, version, description
- Project root path
- Extension path (to copy into chrome://extensions/ -> Load unpacked)
- HTTP bridge ports in use
- Available commands (setup / run / sync / dev)
- Alias configuration hint (the user adds it themselves)

Run:
    python3 scripts/about.py
Or via the wrapper:
    ./run --about
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


class About:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.extension_dir = self.project_root / "runctx-extension"
        self.manifest_path = self.extension_dir / "manifest.json"
        self.package_path = self.project_root / "package.json"

    def _load_json(self, path: Path) -> dict:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def collect(self) -> dict:
        package = self._load_json(self.package_path)
        manifest = self._load_json(self.manifest_path)

        ports = self._extract_ports(manifest)

        return {
            "name": package.get("name", "sonsery-flow"),
            "version": package.get("version", manifest.get("version", "unknown")),
            "description": package.get("description", ""),
            "project_root": str(self.project_root),
            "extension_dir": str(self.extension_dir),
            "extension_exists": self.extension_dir.is_dir(),
            "manifest_version": manifest.get("manifest_version"),
            "ports": ports,
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.release()}",
        }

    @staticmethod
    def _to_windows_path(path: Path) -> str | None:
        """Convert a Linux path to a WSL UNC path to paste into Explorer.

        Returns None when not running under WSL.
        Example: /home/sonnguyen/projects -> \\\\wsl.localhost\\Ubuntu\\home\\sonnguyen\\projects
        """
        distro = os.environ.get("WSL_DISTRO_NAME")
        if not distro:
            return None
        linux_path = str(path).replace("/", "\\")
        if not linux_path.startswith("\\"):
            linux_path = "\\" + linux_path
        return f"\\\\wsl.localhost\\{distro}{linux_path}"

    def _extension_paths(self, ext_dir: str) -> dict:
        """Compute the extension path for every supported OS.

        Always returns all three so the printed block can show whichever
        one the reader needs, regardless of the machine running the script.
        """
        posix = Path(ext_dir)
        root = self.project_root

        # macOS / Linux native: same POSIX path.
        posix_path = str(posix)

        # Windows native: convert POSIX -> drive letter using project root.
        # Best-effort: swap the project root prefix for a placeholder drive
        # since we cannot know the real drive letter when running on WSL/Linux.
        windows_native = None
        if platform.system() == "Windows":
            windows_native = str(posix)
        else:
            # Hint form for people who cloned on Windows (D:\projects\...).
            rel = posix.relative_to(root) if root in posix.parents else None
            if rel is not None:
                rel_win = str(rel).replace("/", "\\")
                windows_native = f"<drive>:\\projects\\sonsery-flow\\{rel_win}"

        # WSL: UNC into Explorer + the underlying Linux path.
        wsl_unc = self._to_windows_path(posix)
        if not wsl_unc:
            distro = os.environ.get("WSL_DISTRO_NAME", "<Distro>")
            linux_fwd = posix_path.replace("/", "\\")
            wsl_unc = f"\\\\wsl.localhost\\{distro}{linux_fwd}"

        return {
            "macos": posix_path,
            "windows": windows_native,
            "wsl_unc": wsl_unc,
            "wsl_linux": posix_path,
        }

    def _extension_block(self, info: dict) -> list:
        """Render the extension path block with a branch per OS.

        All three branches are printed every time so the reader can pick
        the path that matches their Explorer (each machine may differ).
        """
        out = []
        line = "=" * 60
        out.append(line)
        out.append("  CHROME EXTENSION")
        out.append(line)

        if not info["extension_exists"]:
            out.append("  [WARNING] runctx-extension/ folder not found")
            out.append(f"  Expected at: {info['extension_dir']}")
            out.append("")
            return out

        paths = self._extension_paths(info["extension_dir"])

        out.append("  Copy the path matching YOUR machine into 'Load unpacked':")
        out.append("")

        out.append("  [WINDOWS]  Explorer address bar:")
        if paths["windows"]:
            out.append(f"    {paths['windows']}")
        else:
            out.append(
                "    (clone on Windows to get the real drive, e.g. D:\\projects\\sonsery-flow\\runctx-extension)"
            )
        out.append("")

        out.append("  [macOS]    Copy directly into Load unpacked:")
        out.append(f"    {paths['macos']}")
        out.append("")

        out.append("  [WSL]      Explorer -> Load unpacked (UNC):")
        out.append(f"    {paths['wsl_unc']}")
        out.append("")
        out.append("  [WSL]      Linux path (terminal / reference):")
        out.append(f"    {paths['wsl_linux']}")
        out.append("")

        out.append("  How to install:")
        out.append("    1. Open chrome://extensions/")
        out.append("    2. Enable 'Developer mode'")
        out.append("    3. Click 'Load unpacked' -> paste the path for your OS")
        out.append("")
        return out

    @staticmethod
    def _extract_ports(manifest: dict) -> list:
        ports = set()
        for perm in manifest.get("host_permissions", []):
            if "127.0.0.1:" in perm:
                try:
                    ports.add(int(perm.rstrip("/*").rsplit(":", 1)[1]))
                except (ValueError, IndexError):
                    continue
        return sorted(ports)

    def _alternative_hint(self) -> list:
        """Render the 'run without alias' block, per OS.

        The POSIX form (python3 + single quotes) only works on bash/zsh.
        Windows needs `py`/`python` + double quotes + backslash paths.
        """
        root = self.project_root
        root_posix = str(root)
        root_win = str(root).replace("/", "\\")
        system = platform.system()
        is_wsl = bool(os.environ.get("WSL_DISTRO_NAME"))

        out = ["  Alternative (no alias needed):"]

        if is_wsl:
            out.append("    # WSL (bash):")
        elif system == "Windows":
            out.append("    # Windows (PowerShell / cmd) -- use 'py' or 'python':")
            out.append(f'    py "{root_win}\\watchctx.py"       # Run watchctx directly')
            out.append(f'    py "{root_win}\\sync-prompts.py"   # Sync prompts')
            out.append("")
            out.append("    # If 'py' is not on PATH, try 'python' instead.")
            return out
        elif system == "Darwin":
            out.append("    # macOS (bash/zsh) -- needs Xcode Command Line Tools for python3:")
            out.append("    # If 'python3' is missing:  xcode-select --install")
        else:
            out.append("    # Linux (bash/zsh):")

        out.append(f"    python3 '{root_posix}/watchctx.py'       # Run watchctx directly")
        out.append(f"    python3 '{root_posix}/sync-prompts.py'   # Sync prompts")
        return out

    def _alias_hint(self) -> list:
        """Suggest alias configuration (the user adds it to their rc file)."""
        root = self.project_root
        is_windows = platform.system() == "Windows"
        if is_windows:
            return [
                "  # PowerShell ($PROFILE):",
                f'  function watchctx      {{ & "{root}\\run.bat" @args }}',
                f'  function watchctx-sync {{ & "{root}\\sync.bat" @args }}',
                "",
                "  # Or run directly inside the project:",
            ]
        return [
            "  # bash/zsh (~/.bashrc or ~/.zshrc):",
            f"  alias watchctx='{root}/run'",
            f"  alias watchctx-sync='{root}/sync'",
            "",
            "  # Or a function (more flexible):",
            f"  watchctx()      {{ python3 '{root}/watchctx.py' \"$@\"; }}",
            f"  watchctx-sync() {{ python3 '{root}/sync-prompts.py' \"$@\"; }}",
            "",
            "  # Or run directly inside the project:",
        ]

    def render(self, info: dict) -> str:
        line = "=" * 60
        ports = info["ports"]
        ports_str = f"{ports[0]}-{ports[-1]} ({len(ports)} ports)" if ports else "unknown"

        out = []
        out.append(line)
        out.append(f"  {info['name']}  v{info['version']}")
        out.append(line)
        out.append(f"  Description  : {info['description']}")
        out.append(f"  Project root : {info['project_root']}")
        out.append(f"  Platform     : {info['platform']}")
        out.append(f"  Python       : {info['python']}")
        out.append("")
        out.extend(self._extension_block(info))
        out.append(line)
        out.append("  HTTP BRIDGE")
        out.append(line)
        out.append(f"  Ports        : {ports_str}")
        out.append("")
        out.append(line)
        out.append("  AVAILABLE COMMANDS")
        out.append(line)
        out.append("  pnpm setup                 # End-user setup (venv + wrapper)")
        out.append("  pnpm setup:dev             # Dev setup (test/lint tooling)")
        out.append("  ./run                       # Run watchctx (clipboard + HTTP bridge)")
        out.append("  ./sync                      # Sync prompts into the extension")
        out.append("  pnpm check                  # Run full lint + format + typecheck + test")
        out.append("")
        out.extend(self._alternative_hint())
        out.append("")
        out.append(line)
        out.append("  ALIAS (OPTIONAL)")
        out.append(line)
        out.append("  Setup NEVER writes aliases. To run 'watchctx' from any directory,")
        out.append("  add the following lines to your shell config:")
        out.append("")
        out.extend(self._alias_hint())
        out.append("")
        out.append(line)
        return "\n".join(out)

    def run(self):
        info = self.collect()
        print(self.render(info))


if __name__ == "__main__":
    About().run()
