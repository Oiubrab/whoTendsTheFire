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
- **Evolution proven.** The fork, the race and the selection are implemented
  and run, but no mutation has yet survived selection on a real run.
- **The dynamo.** No torch mints new torches. All 46 are human-authored.
- **Judgement of quality.** Every gate asks "does it run", never "is it any
  good". A feature that runs and whose own test agrees with it passes, and
  nothing notices that it is useless. This is the largest remaining gap.
- **A supervisor.** If the agent process dies mid-lineage there is no resume;
  the hearth's state is on disk but nothing picks it back up.

## The library

46 torches and 8 graphs, seeded in `q/library.q` from boilerplate that lives
as real files under `assets/`. Not string literals in a q file: a 200-line
dispatcher embedded as an escaped q string cannot be run, linted or tested,
and every earlier version of this project that inlined its scaffold shipped
scaffold that did not work.

The distribution is the point:

| Kind | Count | Who acts |
|------|------:|----------|
| `action` | 18 | nobody — deterministic code |
| `validation` | 12 | nobody — a check, and the exit status decides |
| `authoring` | 12 | the model writes one file against a stated contract |
| `decision` | 3 | the model picks one option from a closed menu |
| `kindling` | 1 | the model picks an arrangement and writes one sentence |

**30 of 46 torches consult no model at all.** That is the ratio principle 5
asks for: a model call is a debt, and the deterministic work is already
written. The scripts in `assets/tools/` are where it went — `survey.py`
derives an inventory from the syntax tree, `tidy.py` removes unused imports,
`docgen.py` writes the documentation by running the program, `smoke.py`
starts the server and hits every declared route, `schemacheck.py` applies
migrations and reads the schema back, `webcheck.py` balances tags and
brackets, `packagecheck.py` resolves the console entry point.

### The arrangements

| Graph | What it does | Authoring torches |
|---|---|--:|
| `g.found` | Pick surface, storage and licence; install everything that follows | 0 |
| `g.feature` | One new command-line subcommand | 3 |
| `g.route` | One new group of HTTP endpoints | 2 |
| `g.view` | One new page in the browser front end | 1 |
| `g.schema` | One new database table, via a migration | 1 |
| `g.fullstack` | A table, the endpoints over it, and the page that shows it | 4 |
| `g.harden` | No new behaviour: tidy, recompile, re-verify, re-document | 0 |
| `g.document` | Regenerate derived docs and check packaging | 0 |

`g.harden` and `g.document` have no authoring torches whatsoever. A
generation that walks one of them spends itself getting strictly better at
what the app already does, and the only model call in it is choosing what
comes next.

### What the model is actually asked

Three things, and nothing else:

1. **Pick one option from a menu** — which surface, which storage, which
   licence. Each option writes a different file or grants a different
   capability, so a choice always has consequences ([02](02-the-graph.md)).
2. **Write one file against a contract** — one feature module, one route
   module, one view, one migration, one test. The torch declares the target
   path, output that does not parse is refused rather than written, and a
   validation torch runs over the result regardless.
3. **Pick an arrangement and write one sentence** — at the kindling torch.
   Its options *are* the library's graph ids, so the menu cannot drift out of
   step with the library, and the menu is filtered by `offerable` so a
   lineage that chose JSON storage is never offered `g.schema`.

### The library checks itself

`libcheck[]` asserts the library's own shape, and `selftest.sh` runs it on
every change. A graph is data, and malformed data here does not raise — it
silently produces a lineage that cannot reproduce, which has happened twice
in this project. It verifies that every declared root really is a root, that
no edge points at a non-member, that every declared option is wired and
nothing undeclared is, that every graph can reach a kindling torch, that
every authoring torch declares a target, and that every decision torch's
options have consequences.

## Running it

**The UI:**

```sh
python3 server.py 8420     # then open http://127.0.0.1:8420
```

**The agent** (requires the bridge running, and Ollama up with `torch-gpt-oss`):

```sh
# runs until the model declines or a hearth ceiling stops it
python3 agent.py "a weather station I can run at home"

python3 agent.py "..." --generations 5   # stop after five prophecies
python3 agent.py "..." --fresh-dirs      # daughters build alongside, not in place
python3 agent.py "..." --evolve          # breed graph variants at each kindling site
```

**The fast test** — the whole pipeline end to end with a canned model, in
seconds rather than the forty minutes a real run takes:

```sh
bash selftest.sh                  # 27 assertions
sh q/lint.sh                      # the one q landmine that voids a file silently

# aim a canned run at specific arrangements
FAKE_MODEL=1 FAKE_KINDLES="g.fullstack,g.route" python3 agent.py "..." 
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
