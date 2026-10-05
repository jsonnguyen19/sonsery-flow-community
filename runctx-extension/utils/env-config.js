// ============================================================
// ENV CONFIG — SINGLE SOURCE OF TRUTH
// ============================================================
// ⚠️ THIS IS THE ONLY place that defines env-settings constants
// (per-site max response limits + display-name maps for shell /
// tech stack / package manager).
//
// Consumers:
//   - popup/settings.js   (inject button env context + settings UI)
//   - content scripts     (prompt injection env context)
//
// Everywhere reads from window.__RUNCTX_ENV__ instead of hard-coding
// its own copy. To change values, edit ONLY this file.

(function (global) {
  // Per-site max response limits for the "auto" option (keyed by hostname).
  // Sites not listed = unlimited (0), same as DeepSeek.
  const MAX_RESPONSE_AUTO = {
    "chat.deepseek.com": 0,
    "chatgpt.com": 600,
  };

  function resolveMaxResponse(value, hostname) {
    if (value !== "auto") return parseInt(value) || 0;
    // Strip a leading "www." so subdomain mirrors (e.g. www.chatgpt.com)
    // still match the exact keys above.
    const host = String(hostname || "").replace(/^www\./, "");
    return MAX_RESPONSE_AUTO[host] ?? 0;
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
    MAX_RESPONSE_AUTO,
    resolveMaxResponse,
    SHELL_DISPLAY,
    TECH_DISPLAY,
    PM_DISPLAY,
    getShellDisplay,
    getTechDisplay,
    getPmDisplay,
  };
})(typeof window !== "undefined" ? window : self);
