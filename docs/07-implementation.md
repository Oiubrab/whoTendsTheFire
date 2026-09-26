# 07 — Implementation

What actually exists and runs today, as distinct from what the rest of these documents describe. Everything in [04](04-the-lineage.md) about kindling and everything in [05](05-evolution.md) is design, not code.

## What's real

| Component | File | State |
|-----------|------|-------|
| Graph engine and store | `q/torches.q` | Working. Schema, walking, capability gating, execution, prophecy state, persistence. |
| HTTP bridge | `server.py` | Working. Stdlib only, no dependencies. |
| Browser UI | `ui/index.html` | Working. Force-directed graph, live lighting, sidebar state. |
| Local-model agent | `agent.py` | Working. Drives a full prophecy with no human input. |
| Model | `models/gpt-oss-20b-Q8_0.gguf` | Imported into Ollama as `torch-gpt-oss`. |

A full prophecy — invocation to working, executable code — runs end to end with every decision made by a model on this machine.

## What's not

- **Kindling.** No torch produces a daughter prophecy. A prophecy ends and waits for a person.
- **The dynamo.** No torch mints new torches. The graph is entirely human-authored.
- **Evolution mode.** No local library, no candidates, no races, no selection.
- **A library of graphs.** One flat torch table, not named reusable graphs.
- **Real failure routing.** One `fail` edge, which ends the prophecy.
- **Any sandboxing.** Torch code runs directly on the host as the invoking user.

## Running it

**The UI:**

```sh
python3 server.py 8420     # then open http://127.0.0.1:8420
```

**The agent** (requires the bridge running, and Ollama up with `torch-gpt-oss`):

```sh
python3 agent.py "build me a small python cli tool"
```

**The engine alone:**

```sh
q q/torches.q -q
```

Prophecy working directories land in `runs/<pid>/`. Persisted tables live in `db/`. Both are gitignored.

## The q layer

`q/torches.q`. Tables are documented in [02](02-the-graph.md); this is the function surface.

### Graph construction

`addtorch` `addfile` `addtool` `addprovide` `addrequire` `addedge`

Seeded graph is eight torches across two disconnected roots — a Python CLI chain and a Docker-image choice that gates two language-specific writers.

### Similarity

`embed` `cosine` `nearest` — hashing-trick bag-of-words, for finding torches by meaning. Crude by design.

### Walking

| Function | Does |
|----------|------|
| `walk[frm;lbl]` | Raw edge lookup. |
| `capabilities[pid]` | Everything granted by choices so far in a prophecy. |
| `eligible[pid;tid]` | Whether a torch's requirements are satisfied. |
| `walkable[pid;tid;opt]` | `walk`, filtered by `eligible`. What is actually offerable. |
| `roots[]` | Torches with no incoming edge. |

### Execution

| Function | Does |
|----------|------|
| `attempt[cmd]` | Runs a shell command, trapping non-zero exit, returning `(success;output)`. |
| `runin[dest;cmd]` | `attempt` in a directory, restoring the original afterwards. |
| `ensure[tid;opt]` | Probes each required tool, installs if missing, reports per-tool status. |
| `materialize[tid;opt;dest]` | Writes the torch's files for that option. |
| `light[tid;opt;dest]` | The whole sequence. Resolves validation outcomes from `codeOk`. |

### Prophecies

| Function | Does |
|----------|------|
| `begin[pid;invocation;dest]` | Opens a prophecy, seeds the frontier from `roots[]`. |
| `lightin[pid;tid;opt]` | `light` inside a prophecy: enforces the frontier, logs, advances. |
| `state[pid]` | Full snapshot for a UI or agent. |
| `brief` / `briefText` | Model context bundle, structured or rendered. |
| `logchoice` `tree` | Chronicle append; working-directory listing. |
| `savedb` / `loaddb` | Persist and restore all tables. |

## The bridge

`server.py`. Python stdlib only — deliberately, so it runs without a virtualenv or install step. Each request shells out to `q` once, loading persisted state, running one expression, and saving back.

| Method | Path | Returns |
|--------|------|---------|
| GET | `/` | The UI. |
| GET | `/api/graph` | Nodes and edges. |
| GET | `/api/state?pid=` | Full prophecy snapshot. |
| GET | `/api/brieftext?pid=&torch=` | Rendered model context. |
| POST | `/api/begin` | New prophecy: `{invocation}` → `{pid, state}`. |
| POST | `/api/light` | `{pid, torch, option}` → `{result, state}`. |

Frontend and API are same-origin, which avoids the CORS and mixed-content problems a hosted page hitting `localhost` would run into.

## The UI

`ui/index.html`, single file, no external assets or CDN — it works offline.

Nodes coloured by kind. Lit torches glow solid; frontier torches pulse and are clickable; neighbours stay visible but dim so the surrounding graph is legible. Clicking a decision torch opens its rite and options. Clicking a validation torch just lights it — pass/fail is not a choice ([03](03-the-prophecy.md)). Sidebar tracks invocation, capabilities, chronicle, and the live file tree.

Layout is a small hand-rolled force simulation, run once on load.

## The agent

`agent.py`. At each frontier torch it fetches the same `briefText` a human would see, asks the local model to pick one option, and lights it. Loops until the frontier empties or a step budget runs out.

Validation torches skip the model call entirely — the outcome is derived, so asking would be theatre.

### The Harmony quirk

gpt-oss emits OpenAI's Harmony format:

```
<|channel|>analysis<|message|>...reasoning...<|end|>
<|start|>assistant<|channel|>final<|message|>the actual answer
```

Ollama's own `gpt-oss` library models parse this; a bare GGUF import does not, so the raw markup comes through. `agent.py` strips it — split on the last `<|channel|>final<|message|>`, cut at the first stop token.

## kdb+ gotchas hit while building this

Recorded because each one cost real time and none are obvious.

1. **A bare `/` on its own line opens a block comment** that runs until a lone `\`. An unterminated one silently swallows the rest of the file — the script loads with no error and nothing defined. Hit twice.
2. **`from` and `to` are q-sql keywords** and cannot be referenced as bare column names inside a query, though they're legal in a schema. Hence `src`/`dst`.
3. **A lambda parameter sharing a name with a queried column silently shadows it.** `{[torch] exec val from t where torch=torch}` matches every row, always, and returns wrong results rather than erroring.
4. **`?`, `[`, `]` are wildcard metacharacters to `ss`/`ssr`**, not literals. Punctuation stripping has to go through index-based amend.
5. **`system` raises on any non-zero exit**, including a probe that is supposed to fail. Hence `attempt`.
6. **`system "cd X && Y"` is unreliable** — kdb+ special-cases a leading `cd ` into changing its own process directory, so the `&&` is not honoured consistently. Hence `runin`, which also restores the original directory to stop a torch redirecting every later relative path.
7. **`` `key!enlist x `` is a type error.** Single-key dicts need `` (enlist `key)!enlist x ``.
8. **`next` is a reserved word.** So the walk function is `walk`.
