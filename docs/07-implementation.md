# 07 — Implementation

What actually exists and runs today, as distinct from what the rest of these documents describe. [04](04-the-lineage.md) is now largely built; the dynamo within it and all of [05](05-evolution.md) are still design, not code.

## What's real

| Component | File | State |
|-----------|------|-------|
| Graph engine and store | `q/torches.q` | Working. Schema, library, walking, capability gating, execution, prophecies, hearths, kindling, governance, persistence. |
| HTTP bridge | `server.py` | Working. Stdlib only, no dependencies. |
| Browser UI | `ui/index.html` | Working. Force-directed graph, live lighting, kindling, lineage panel. |
| Local-model agent | `agent.py` | Working. Drives a whole hearth across generations with no human input. |
| Model | `models/gpt-oss-20b-Q8_0.gguf` | Imported into Ollama as `torch-gpt-oss`. |

A whole hearth runs end to end with every decision made by a model on this machine: a founding invocation becomes the ember, a prophecy walks its graph to completion, a kindling torch proposes the next thing to build, and a daughter prophecy picks it up — repeating until the model declines or a ceiling stops it.

An observed run, ember *"a weather station I can run at home"*, three generations, entirely unattended:

1. build a small python cli tool
2. *"Implement a CLI command that reads temperature and humidity from a connected sensor (e.g. DHT22 or BMP280) via the Raspberry Pi's GPIO and logs each reading to a local SQLite database for later analysis."*
3. *"Implement a lightweight web server that serves an HTML page displaying the latest sensor readings and historical trends."*

The trajectory is the model's own, each step checked against the ember.

## What's not

- **The dynamo.** No torch mints new torches. The graph is entirely human-authored.
- **Evolution mode.** No local library fork, no candidates, no races, no selection. Blocked on the fitness function ([06](06-open-problems.md)).
- **Real failure routing.** One `fail` edge, which ends the prophecy.
- **Any sandboxing.** Torch code runs directly on the host as the invoking user. This is the thing that most needs fixing before the dynamo is turned on.
- **A daughter that walks a *different* graph.** Kindling can target any graph, but nothing yet chooses one from the invocation — the agent passes the same graph through.

### A caveat about the seeded library

The library is two graphs and eight torches. Every prophecy in the run above walked the same five torches, because that is all there is — the daughters' invocations were good but the library has nothing that could act on "add a web server" differently from "add a sensor reader." The loop is real; the vocabulary it walks is a toy. Growing that is what the dynamo is for.

## Running it

**The UI:**

```sh
python3 server.py 8420     # then open http://127.0.0.1:8420
```

**The agent** (requires the bridge running, and Ollama up with `torch-gpt-oss`):

```sh
python3 agent.py "a weather station I can run at home" --generations 3
python3 agent.py "..." --brownfield     # daughters extend the parent's directory
python3 agent.py "..." --graph g.langpick
```

**The engine alone:**

```sh
q q/torches.q -q
```

Prophecy working directories land in `runs/<hearth>/<pid>/`. Persisted tables live in `db/`. Both are gitignored.

## The q layer

`q/torches.q`. Tables are documented in [02](02-the-graph.md); this is the function surface.

### Graph construction

`addtorch` `addfile` `addtool` `addprovide` `addrequire` `addedge`

`addgraph` declares a graph; every torch names the graph it belongs to. Seeded library is two graphs and eight torches: `g.pycli` (a Python CLI chain ending in a kindling torch) and `g.langpick` (a Docker-image choice gating two language-specific writers).

### Similarity

`embed` `cosine` `nearest` — hashing-trick bag-of-words, for finding torches by meaning. Crude by design.

### Walking

| Function | Does |
|----------|------|
| `walk[frm;lbl]` | Raw edge lookup. |
| `capabilities[pid]` | Everything granted by choices so far in a prophecy. |
| `eligible[pid;tid]` | Whether a torch's requirements are satisfied. |
| `walkable[pid;tid;opt]` | `walk`, filtered by `eligible`. What is actually offerable. |
| `roots[g]` | Root torches of one graph. Listed again under hearths. |

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
| `begin[hid;pid;g;invocation;dest]` | Opens a prophecy inside a hearth, seeds the frontier from `roots[g]`. |
| `lightin[pid;tid;opt]` | `light` inside a prophecy: enforces the frontier, logs, advances. |
| `state[pid]` | Full snapshot for a UI or agent. |
| `brief` / `briefText` | Model context bundle, structured or rendered. |
| `logchoice` `tree` | Chronicle append; working-directory listing. |
| `savedb` / `loaddb` | Persist and restore all tables. |

### Hearths and kindling

| Function | Does |
|----------|------|
| `ignite[hid;ember;evo]` | Lights a hearth: pins the ember, sets the evolution flag, defaults the ceilings (`maxgen` 5, `maxproph` 20, `autokindle` off). |
| `maykindle[hid]` | The brake. Returns `(ok; reason)`. Refuses on autokindle-off, generation ceiling, or prophecy ceiling. |
| `kindle[pid;newpid;g;invocation;dest]` | Creates a daughter prophecy — after checking `maykindle`, which it will not bypass. `dest` is the caller's choice: the parent's own dest extends in place, a fresh one builds alongside. |
| `lineage[hid]` | The whole family tree, generation-ordered. |
| `roots[g]` | Root torches of one graph in the library. |
| `addgraph[gid;purpose]` | Declare a graph in the library. |

## The bridge

`server.py`. Python stdlib only — deliberately, so it runs without a virtualenv or install step. Each request shells out to `q` once, loading persisted state, running one expression, and saving back.

| Method | Path | Returns |
|--------|------|---------|
| GET | `/` | The UI. |
| GET | `/api/graph` | Nodes and edges. |
| GET | `/api/state?pid=` | Full prophecy snapshot. |
| GET | `/api/brieftext?pid=&torch=` | Rendered model context. |
| GET | `/api/graphs` | The library. |
| GET | `/api/lineage?hearth=` | A hearth's family tree. |
| POST | `/api/begin` | Light a hearth: `{invocation, graph, autokindle, evolution}` → `{hearth, pid, state}`. |
| POST | `/api/light` | `{pid, torch, option}` → `{result, state}`. |
| POST | `/api/kindle` | `{pid, invocation, graph, brownfield}` → `{pid, state}`, or `{error}` if the brake refuses. |

Frontend and API are same-origin, which avoids the CORS and mixed-content problems a hosted page hitting `localhost` would run into.

## The UI

`ui/index.html`, single file, no external assets or CDN — it works offline.

Nodes coloured by kind. Lit torches glow solid; frontier torches pulse and are clickable; neighbours stay visible but dim so the surrounding graph is legible. Clicking a decision torch opens its rite and options. Clicking a validation torch just lights it — pass/fail is not a choice ([03](03-the-prophecy.md)). Clicking a kindling torch prompts for the daughter's invocation and moves the view into the new prophecy. Sidebar tracks the ember, this prophecy's invocation and generation, capabilities, chronicle, live file tree, and the lineage so far.

Layout is a small hand-rolled force simulation, run once on load.

## The agent

`agent.py`. At each frontier torch it fetches the same `briefText` a human would see, asks the local model to pick one option, and lights it. At a kindling torch it instead asks for the next thing to build — with the ember included in the prompt — and spawns a daughter, continuing into it. Loops until the model declines, a ceiling refuses, or `--generations` is reached.

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
