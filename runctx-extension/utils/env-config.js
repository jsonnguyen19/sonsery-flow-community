// ============================================================
// ENV CONFIG — SINGLE SOURCE OF TRUTH
// ============================================================
// ⚠️ THIS IS THE ONLY place that defines env-settings constants
// (per-site max result lines for the "auto" option, the sentence that
// tells the AI about the limit, and display-name maps for shell /
// tech stack / package manager).
//
// Consumers:
//   - popup/settings.js   (inject button env context + settings UI)
//   - content scripts     (prompt injection env context)
//
// Everywhere reads from window.__RUNCTX_ENV__ instead of hard-coding
// its own copy. To change values, edit ONLY this file.

(function (global) {
  // Per-site max result lines for the "auto" option (keyed by hostname).
  // chatgpt.com refuses pasted input beyond ~2000 lines, so keep headroom for
  // the JSON wrapper and the rest of the message.
  // Sites not listed = unlimited (0), same as DeepSeek.
  const MAX_LINES_AUTO = {
    "chat.deepseek.com": 0,
    "chatgpt.com": 1500,
  };

  function resolveMaxLines(value, hostname) {
    // Unset (settings never saved) behaves like "auto".
    if (value != null && value !== "auto") return parseInt(value) || 0;
    // Strip a leading "www." so subdomain mirrors (e.g. www.chatgpt.com)
    // still match the exact keys above.
    const host = String(hostname || "").replace(/^www\./, "");
    return MAX_LINES_AUTO[host] ?? 0;
  }

  // The sentence injected into the [ENV: ...] block. Written for the AI: it says
  // what the number means (lines of output/content, per result) and how to get
  // the rest when a result is cut. Keep in sync with the maxLines rule in
  // prompts/*.txt and runctx/max_lines.py.
  function getMaxLinesInstruction(maxLines) {
    return `every payload must include "maxLines": ${maxLines} (each result returns at most ${maxLines} lines of output/content in total; if an item has "truncated", send a new payload for the rest starting at "next_start")`;
  }

  const SHELL_DISPLAY = {
    auto: "Auto-detect",
    bash: "Bash",
    zsh: "Zsh",
    powershell: "PowerShell",
    cmd: "CMD",
    gitbash: "Git Bash",
  };

  const TECH_DISPLAY = {
    auto: "Auto-detect",
    node: "Node.js",
    react: "React",
    vue: "Vue",
    angular: "Angular",
    python: "Python",
    dotnet: ".NET",
    go: "Go",
    rust: "Rust",
    java: "Java",
    php: "PHP",
    ruby: "Ruby",
    other: "Other",
  };

  const PM_DISPLAY = {
    auto: "Auto-detect",
    npm: "npm",
    pnpm: "pnpm",
    yarn: "yarn",
    pip: "pip",
    poetry: "poetry",
    pipenv: "pipenv",
    dotnet: "dotnet",
    go: "go mod",
    cargo: "cargo",
    gradle: "gradle",
    maven: "maven",
    composer: "composer",
    bundler: "bundler",
    other: "Other",
  };

  function getShellDisplay(shell) {
    return SHELL_DISPLAY[shell] || shell;
  }

  function getTechDisplay(tech) {
    return TECH_DISPLAY[tech] || tech;
  }

  function getPmDisplay(pm) {
    return PM_DISPLAY[pm] || pm;
  }

  global.__RUNCTX_ENV__ = {
    MAX_LINES_AUTO,
    resolveMaxLines,
    getMaxLinesInstruction,
    SHELL_DISPLAY,
    TECH_DISPLAY,
    PM_DISPLAY,
    getShellDisplay,
    getTechDisplay,
    getPmDisplay,
  };
})(typeof window !== "undefined" ? window : self);
