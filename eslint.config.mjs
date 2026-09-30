// ESLint flat config for runctx-extension
// Run: pnpm lint:js
//
// Note: runctx-extension scripts share a global scope (no ES modules), so
// every cross-file global must be declared here.

import js from "@eslint/js";
import globals from "globals";

// Functions/consts exposed via window.* and used cross-file
const runctxGlobals = {
  // popup/prompts.js (auto-gen)
  AGENTCTX_CONTENT: "readonly",
  // popup/tokens.js
  TOKEN_STORAGE_KEY: "readonly",
  estimateTokens: "readonly",
  getDefaultTokenState: "readonly",
  getTokenState: "readonly",
  resetTokenSession: "readonly",
  renderTokenStats: "readonly",
  // popup/settings.js
  SETTINGS_KEY: "readonly",
  getEnvSettings: "readonly",
  saveEnvSettings: "readonly",
  getShellDisplay: "readonly",
  getTechDisplay: "readonly",
  getPmDisplay: "readonly",
  buildEnvironmentContext: "readonly",
  updateSettingsFromUI: "readonly",
  loadSettingsToUI: "readonly",
  setupSettingsAutoSave: "readonly",
  // utils/speed-config.js
  __RUNCTX_SPEED__: "readonly",
  // popup/speed.js
  SPEED_MODE_KEY: "readonly",
  DEFAULT_SPEED_MODE: "readonly",
  SPEED_FACTORS: "readonly",
  normalizeSpeedMode: "readonly",
  getSpeedFactorFromMode: "readonly",
  getSpeedMode: "readonly",
  getSpeedFactor: "readonly",
  saveSpeedMode: "readonly",
  // popup/helpers.js
  getActiveTab: "readonly",
  autoCollapseSidebar: "readonly",
  toastInTab: "readonly",
  runInTab: "readonly",
  injectContext: "readonly",
  getCurrentInputContent: "readonly",
  // popup/tabs.js
  setupTabs: "readonly",
  renderPinBtn: "readonly",
  updateManualControls: "readonly",
  renderBadge: "readonly",
  render: "readonly",
  // popup/actions.js
  sendStateToTab: "readonly",
  setupPinButton: "readonly",
  setupManualControls: "readonly",
  setupInjectButton: "readonly",
  setupShowToastsToggle: "readonly",
  loadShowToastsState: "readonly",
  setupPlayResultSoundToggle: "readonly",
  loadPlayResultSoundState: "readonly",
  setupResetTokensButton: "readonly",
};

export default [
  {
    ignores: [
      "node_modules/**",
      ".venv/**",
      ".venv-test/**",
      "venv/**",
      "runctx-extension/popup/prompts.js", // AUTO-GEN by sync-prompts.py
      "**/*.min.js",
      // tests/ holds fixtures for the e2e skill (files the AI reads/edits),
      // not shipped code. They are not linted (see lint:js scope) so the
      // editor should not flag them either.
      "tests/**",
    ],
  },
  js.configs.recommended,
  {
    files: ["runctx-extension/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        // Chrome Extension APIs
        chrome: "readonly",
        // Service worker API (background.js) — self, importScripts
        self: "readonly",
        importScripts: "readonly",
        // Global bridge namespaces
        __RUNCTX__: "writable",
        __RUNCTX_POPUP__: "writable",
        // Cross-file globals
        ...runctxGlobals,
      },
    },
    rules: {
      "no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "no-empty": ["error", { allowEmptyCatch: true }],
      "no-cond-assign": "warn",
      eqeqeq: ["warn", "smart"],
      "no-var": "warn",
      "prefer-const": "warn",
      // Scripts share a global scope (no ES modules) -> disable no-redeclare
      // for the globals declared above (intentional cross-file globals).
      "no-redeclare": ["error", { builtinGlobals: false }],
      // New ESLint 10 rule, too aggressive for complex control flow -> off.
      "no-useless-assignment": "off",
    },
  },
  {
    // Test files use ES modules (vitest) — placed AFTER the general block to
    // override sourceType: script into module.
    files: ["runctx-extension/**/__tests__/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
];
