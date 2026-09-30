# Scripts

## `about.py` — Tool info

Prints basic information about the tool: name, version, description, project root, and
the **absolute path of the extension** (copy into `chrome://extensions/` ->
Load unpacked), the list of HTTP bridge ports, and the available commands.

```bash
python3 scripts/about.py
pnpm about
./run --about     # or ./run -a
```

## Setup scripts

Two setup scripts for 2 different audiences:

## `setup.py` — End-user setup

Installs to **run the tool**:
- Create `venv/`
- Install runtime deps from `requirements.txt` (pyyaml, requests)
  (setup does NOT write to the rc file or create shims/pointers — the user chooses how
  to configure it)
- Print Chrome extension instructions

```bash
python3 scripts/setup.py
```

Then:
```bash
./run          # Run watchctx (clipboard watcher + HTTP bridge)
./sync         # Sync prompts into the extension
```

See detailed alias instructions in `README.md` (section "Aliases (optional)")

## `setup-dev.sh` — Dev setup

Installs to **dev/test/lint**:
- Create `.venv-test/`
- Install all dev deps from `requirements-dev.txt` (pytest, ruff, basedpyright, pyyaml, requests)

```bash
pnpm setup:dev        # or
bash scripts/setup-dev.sh
```

**Mirror:** defaults to Aliyun (faster than the original PyPI in VN). Override with env:
```bash
# Use the original PyPI
PIP_INDEX_URL=https://pypi.org/simple/ bash scripts/setup-dev.sh

# Turn off the mirror (equivalent to the original PyPI)
PIP_INDEX_URL="" bash scripts/setup-dev.sh
```

Then use the commands in `package.json`:
```bash
pnpm lint / pnpm format / pnpm typecheck / pnpm test / pnpm check
```

## Differences

| | `setup.py` | `setup-dev.sh` |
|---|---|---|
| Audience | End-user | Dev |
| Venv | `venv/` | `.venv-test/` |
| Deps | `requirements.txt` | `requirements-dev.txt` |
| `run`/`sync` wrappers | Yes | No |
