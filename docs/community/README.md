# Community docs

Docs in this folder ship into the **Community repo** (the public MIT build).
They are the single source of truth for that build: edit them here in the Pro
repo, then run `pnpm sync:community` to publish — never edit the Community repo
directly.

## Contents

| Doc | What it covers |
|---|---|
| [`getting-started.md`](getting-started.md) | Install the backend + extension, run the first automation loop |
| [`architecture.md`](architecture.md) | How the content script, watcher, and bridge fit together |
| [`tabs.md`](tabs.md) | The 4 side-panel tabs and what each one does |
| [`adapters.md`](adapters.md) | The 5 AI adapters + how to debug/add one |
| [`tools.md`](tools.md) | Payload & response format for `shell` / `read` / `replace` / `write`, plus the bridge endpoints |

These docs are maintained in the upstream repo and copied here by the build
script — do not edit them in this repo directly.
