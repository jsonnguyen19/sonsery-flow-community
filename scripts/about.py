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
        root = info["project_root"]

        out = []
        out.append(line)
        out.append(f"  {info['name']}  v{info['version']}")
        out.append(line)
        out.append(f"  Description  : {info['description']}")
        out.append(f"  Project root : {info['project_root']}")
        out.append(f"  Platform     : {info['platform']}")
        out.append(f"  Python       : {info['python']}")
        out.append("")
        out.append(line)
        out.append("  CHROME EXTENSION")
        out.append(line)
        if info["extension_exists"]:
            windows_path = self._to_windows_path(Path(info["extension_dir"]))
            if windows_path:
                out.append("  Path (copy into Explorer / Load unpacked):")
                out.append(f"    {windows_path}")
                out.append("")
                out.append("  Linux path (for reference):")
                out.append(f"    {info['extension_dir']}")
            else:
                out.append("  Path (copy into Load unpacked):")
                out.append(f"    {info['extension_dir']}")
            out.append("")
            out.append("  How to install:")
            out.append("    1. Open chrome://extensions/")
            out.append("    2. Enable 'Developer mode'")
            out.append("    3. Click 'Load unpacked' -> paste the path above into Explorer")
        else:
            out.append("  [WARNING] runctx-extension/ folder not found")
            out.append(f"  Expected at: {info['extension_dir']}")
        out.append("")
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
        out.append("  Alternative (no alias needed):")
        out.append(f"    python3 '{root}/watchctx.py'       # Run watchctx directly")
        out.append(f"    python3 '{root}/sync-prompts.py'   # Sync prompts")
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
