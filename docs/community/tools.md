# Tools — payload & response format

A **payload** is the JSON block the AI emits. `watchctx` runs it and publishes a
**result**.

Every payload must have:

- `id` — an integer (millisecond Unix timestamp). Missing/wrong type → the
  payload is rejected as invalid.
- `tool` — one of `shell`, `read`, `replace`, `write`.

YAML payloads are also accepted (`tool: shell` on its own line).

---

## `shell`

Run one or more shell commands.

```json
{
  "id": 1791016717000,
  "tool": "shell",
  "mode": "sequential",
  "commands": ["ls", "pwd"]
}
```

| Field | Meaning |
|---|---|
| `commands` | Array of command strings (required) |
| `mode` | `sequential` (default) or `parallel` |

Each command is registered as a sub-run `'<id>:<index>'` so it can be listed and
killed through the bridge (`GET /subruns`, `POST /subruns/kill`).

Result item: `{ command, exit_code, output }` (`output` is stdout+stderr).

---

## `read`

Read one file or several.

```json
{
  "id": 1791016717001,
  "tool": "read",
  "files": [
    { "path": "src/app.js", "start": 10, "end": 40 },
    { "path": "package.json" }
  ]
}
```

- `files[].path` required; `start` / `end` are 1-based, optional (omit to read
  the whole file).
- A single-path form is also accepted: `{ "id": …, "tool": "read", "path": "…" }`.

Result item: `{ path, success, content }` (or `{ path, success: false, error }`).

---

## `replace`

Search-and-replace inside a file. The `search` string must match **exactly once**.

```json
{
  "id": 1791016717002,
  "tool": "replace",
  "files": [
    { "path": "src/app.js", "search": "const API = 'old'", "replace": "const API = 'new'" }
  ]
}
```

If `search` matches 0 or >1 times, that file is not modified and the result
reports the actual match count.

Result item (success): `{ path, success: true, message }`.
Result item (failure): `{ path, success: false, error, search, matches }`.

---

## `write`

Write full file contents. A trailing newline is appended automatically.

```json
{
  "id": 1791016717003,
  "tool": "write",
  "files": [
    { "path": "notes.txt", "content": "hello\n" }
  ]
}
```

Result item: `{ path, success: true, message }`.

---

## Response envelope

Every result has this shape:

```json
{ "success": true, "data": [ /* one item per file/command */ ], "error": null }
```

`success` is the AND of every item's success; `error` is a short summary
(`"Some replacements failed"`) or `null`.

Full per-tool examples: see the handler output in `runctx/handlers.py`.

---

## Bridge (read-only HTTP)

`watchctx` exposes a small local HTTP server on `127.0.0.1` (first free port in
8765–8785). The extension uses it; you can too:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/result` | Latest result |
| `POST` | `/result/consume` | Consume the latest result |
| `GET` | `/log?since=&limit=` | watchctx log tail |
| `GET` | `/state` | pwd / active root / bridge port |
| `GET` | `/subruns` | Active shell sub-runs |
| `POST` | `/subruns/kill` | Kill a sub-run by id |
| `POST` | `/rpc` | Synchronous RPC (history tools) |
| `POST` | `/shutdown` | Stop the watcher |

The `POST /rpc` body is `{ id, tool, params }`; `tool` must be in the backend
whitelist. History tools (`get_history`, `get_history_detail`, `clear_history`,
`set_history_cap`) are the ones the Community panel uses.
