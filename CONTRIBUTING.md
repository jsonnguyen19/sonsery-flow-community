# Contributing to Sonsery Flow Community

Thanks for taking the time to contribute! This project is MIT-licensed and
community-driven. Whether you file a bug, propose a feature, improve docs, or
send a pull request — every contribution counts.

> **Project links** — [Landing page](https://flow.sonsery.online/) ·
> [Author portfolio](https://jasonnguyen.website/) ·
> [LinkedIn](https://www.linkedin.com/in/son-nguyen-650628344/) ·
> [Issues](https://github.com/jsonnguyen19/sonsery-flow-community/issues) ·
> Discord: coming soon.

---

## Code of Conduct

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
Please report unacceptable behavior to the maintainers via a private channel
(see [SECURITY.md](SECURITY.md) for contact options).

---

## Ways to contribute

- **Report a bug** — open an issue using the *Bug report* template.
- **Request a feature** — open an issue using the *Feature request* template.
- **Improve documentation** — README, `docs/`, inline comments, examples.
- **Send a pull request** — fix a bug, add a test, refactor, translate.
- **Share the project** — star the repo, write a blog post, tell a friend.

---

## Development setup

### Prerequisites

- **Python 3.8+**
- **Node 18+** and **pnpm 8+** (dev tooling: ESLint, Prettier, Vitest, Husky)
- **Chrome** or **Edge** (to load the extension)

### One-time setup

```bash
# 1. Clone your fork
git clone git@github.com:<your-user>/sonsery-flow-community.git
cd sonsery-flow-community

# 2. Install dev deps (Husky pre-commit hook is installed by "prepare")
pnpm install

# 3. Create the Python test venv
pnpm setup:dev
```

### Run the full check suite

```bash
pnpm check
```

This runs:

- `pnpm lint` — Ruff lint (Python)
- `pnpm lint:js` — ESLint (extension JS)
- `pnpm format:check` — Ruff format check
- `pnpm format:js:check` — Prettier check
- `pnpm typecheck` — BasedPyright
- `pnpm test` — Pytest

Everything must pass before a PR is merged.

---

## Project layout

```
watchctx.py           Entrypoint: clipboard watcher + HTTP bridge
runctx_core.py        Entrypoint: payload processing facade
runctx/               Main Python package
runctx-extension/     Chrome/Edge extension (MV3)
prompts/              Prompt templates (agentctx.txt, ...)
scripts/              Setup + tooling scripts
tests/                Pytest suite + JS e2e tests
docs/                 Design docs and feature specs
```

---

## Coding guidelines

### Python

- Style is enforced by **Ruff** (`pyproject.toml`). Line length 100, target 3.8.
- Imports are sorted by Ruff (`I` rule).
- Prefer explicit typing where it improves clarity; `basedpyright` runs in CI.
- No new runtime dependencies without prior discussion in an issue.

### JavaScript (extension)

- Style is enforced by **ESLint** + **Prettier**.
- The content script runs in an isolated world — no globals from the page.
- New adapters must register in `runctx-extension/adapters/index.js` and add the
  host to `manifest.json` `host_permissions` + `content_scripts.matches`.

### Markdown

- Formatted by Prettier.
- Use fenced code blocks with a language tag.

---

## Commit messages

We loosely follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Kimi adapter
fix(shell): handle CRLF output on Windows
docs(readme): clarify alias setup
chore(i18n): translate Vietnamese comments to English
```

Allowed types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `build`, `ci`.

---

## Pull request process

1. **Fork** the repo and create a topic branch from `main`.
2. Make your change with tests where it makes sense.
3. Run `pnpm check` locally — all checks must pass.
4. Open a PR using the template. Fill in the *What* / *Why* / *How tested* sections.
5. A maintainer will review. Expect at least one round of feedback.
6. Once approved and green, the maintainer merges (squash by default).

### PR checklist

- [ ] Tests added or updated for behavior changes.
- [ ] `pnpm check` passes locally.
- [ ] Docs updated (README, `docs/`, inline comments) when relevant.
- [ ] No secrets, tokens, or personal paths in the diff.
- [ ] Commit history is clean (rebased on `main`).

---

## Reporting security issues

Do **not** open a public issue for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for the private disclosure process.

---

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
