#!/usr/bin/env node
/**
 * Cross-platform Python tool shim.
 *
 * Resolves the correct venv bin dir (POSIX `.venv-test/bin/` vs Windows
 * `.venv-test/Scripts/`) and execs the requested tool, so `pnpm lint`,
 * `pnpm test`, `pnpm typecheck`, lint-staged hooks, etc. all work identically
 * on Linux / macOS / Windows.
 *
 * Usage:
 *   node scripts/py.js <tool> [args...]
 *   node scripts/py.js python -m pytest -v
 *   node scripts/py.js ruff check .
 *   node scripts/py.js basedpyright
 *
 * `tool` is one of the venv-provided executables: python, ruff, basedpyright,
 * pytest, pip. Unknown tools are passed through as-is (still resolved inside
 * the venv bin dir).
 *
 * Exit code is forwarded verbatim so CI / pre-commit hooks fail correctly.
 */

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const PROJECT_ROOT = path.resolve(__dirname, '..')

/**
 * Pick the venv bin dir for the current platform.
 * - Windows: `.venv-test/Scripts/`
 * - POSIX (Linux/macOS/WSL): `.venv-test/bin/`
 *
 * Falls back to the other one if the expected dir is missing (defensive:
 * a venv created under WSL and then accessed from Windows, or vice versa).
 */
function resolveVenvBin() {
  const candidates =
    process.platform === 'win32'
      ? ['Scripts', 'bin']
      : ['bin', 'Scripts']

  for (const sub of candidates) {
    const dir = path.join(PROJECT_ROOT, '.venv-test', sub)
    if (fs.existsSync(dir)) return dir
  }

  // Last resort: report the expected POSIX path so the error message is clear.
  return path.join(PROJECT_ROOT, '.venv-test', candidates[0])
}

/**
 * Append `.exe` on Windows when the tool has no extension yet.
 * venv on Windows ships `python.exe`, `ruff.exe`, `basedpyright.exe`, ...
 */
function resolveToolPath(binDir, tool) {
  const hasExt = path.extname(tool) !== ''
  const exeSuffix = process.platform === 'win32' && !hasExt ? '.exe' : ''
  return path.join(binDir, tool + exeSuffix)
}

function main() {
  const [tool, ...args] = process.argv.slice(2)

  if (!tool) {
    console.error('usage: node scripts/py.js <tool> [args...]')
    process.exit(2)
  }

  const binDir = resolveVenvBin()
  const toolPath = resolveToolPath(binDir, tool)

  if (!fs.existsSync(toolPath)) {
    console.error(
      `[py.js] tool not found: ${toolPath}\n` +
        `        Did you run \`pnpm setup:dev\`?`
    )
    process.exit(127)
  }

  const result = spawnSync(toolPath, args, {
    stdio: 'inherit',
    cwd: PROJECT_ROOT,
    env: process.env,
  })

  if (result.error) {
    console.error(`[py.js] failed to spawn ${toolPath}: ${result.error.message}`)
    process.exit(1)
  }

  // Forward signal or exit code verbatim so CI/pre-commit behave correctly.
  if (result.signal) {
    process.kill(process.pid, result.signal)
    return
  }
  process.exit(result.status ?? 1)
}

main()
