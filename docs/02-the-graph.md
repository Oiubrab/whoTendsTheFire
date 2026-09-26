# 02 — The graph

The graph is the whole system. The engine that walks it knows nothing about what any torch means; that knowledge lives entirely in data. A new capability is new rows in a database, and the engine never changes to accommodate it.

## Torches

A torch is a node. Three kinds, and the kind determines who acts:

| Kind | Who acts | What it does |
|------|----------|--------------|
| `decision` | the model | Offered a finite enumerated set of options; returns exactly one. |
| `action` | the framework | Runs deterministic code — writes files, installs tools, runs a build step. |
| `validation` | the framework | Runs a check. Branches on what actually happened. |

A torch is a self-contained module, not a label. It carries:

- **rite** — the prompt handed to the model at this torch, if any
- **code** — a glue script it runs beyond writing its files
- **files** — the boilerplate it writes into the working directory
- **toolreqs** — what must be installed for it to work, with a probe and an install command
- **options** — its labelled outgoing edges
- **provides / requires** — capability declarations (below)

### Option scoping

`files` and `toolreqs` rows are scoped to a specific option. Picking `flags` at an argument-style decision writes a genuinely different file than picking `positional` — the two variants live directly on that one torch, rather than requiring a separate downstream torch per branch.

A row scoped to the generic empty symbol (`` ` ``) applies no matter which option was taken. That's the normal case for action and validation torches, which only have one real path.

**A choice must have consequences attached to it.** If picking A versus B changes nothing about what gets written or installed, it was not a real decision and should not have been a decision torch.

## Edges

Edges are outcomes, not arrows drawn for convenience.

- A decision torch has one outgoing edge per option offered.
- An action torch typically has one (`done`).
- A validation torch has a `pass` edge and — this is the part that matters — a *separate* `fail` edge per class of failure, each landing on a torch built to handle that specific problem.

A wrong import and a broken architecture do not both loop back to "try again." They go to different places, because they are different problems. Generic retry is the failure mode this design exists to avoid.

An edge may name more than one destination for the same option. Graph-reachable is not the same as actually offerable — see capabilities.

## Capabilities

Two tables, doing opposite jobs:

- **`provides`** — what a chosen option grants. Picking a Python base image provides `python3`.
- **`requires`** — what a torch needs already granted before it is reachable at all. A torch that writes a Python script requires `python3`.

This is distinct from `toolreqs`, and the distinction is load-bearing:

| | `toolreqs` | `provides` / `requires` |
|---|---|---|
| Question | "is this installed on the host?" | "did an earlier choice make this possible?" |
| Effect | probes, and installs if missing | narrows what the graph will even offer next |
| Timing | when the torch runs | before the torch is offered |

**Why this matters:** raw reachability and real availability diverge. A decision torch may have edges to both a Python-writing torch and a Node-writing torch on *both* of its options. `walk` returns both. But once the prophecy has actually chosen a Python image, only `python3` is in the capability set, the Node torch's requirement is unsatisfied, and it is silently not offered. The choice narrowed the world, which is what a choice is supposed to do.

## Graphs and the library

A **graph** is a named, reusable arrangement of torches for a class of work — not the whole torch universe. The **library** is the collection of them.

This layer does not exist in the current implementation, which has a single flat torch table. It is required by [evolution mode](05-evolution.md), which forks a library and mutates individual graphs within it, and it is generally useful: a prophecy should select the graph that fits its invocation rather than navigating one enormous undifferentiated graph.

Likely shape of a library, by the categories a real build needs:

- api graphs (talk to an external service) and an internet-access graph they depend on
- backend graphs
- frontend graphs
- database graphs
- integration graphs (wire new work into an existing codebase)

**Open:** whether "integration" is a separate category at all, or whether every torch should be written brownfield — assuming an existing codebase and extending it — which would collapse the distinction. See [06](06-open-problems.md).

## Current schema

As implemented in `q/torches.q`. Keyed table first, then flat tables.

```q
torches: ([id:`symbol$()]
  kind:      `symbol$();   / `decision `action `validation
  rite:      ();           / prompt for the model at this torch
  code:      ();           / glue script run beyond its files
  options:   ();           / symbol list of labelled outgoing edges
  embedding: () )          / bag-of-words vector, for nearest[]

files:    ([] torch:`symbol$(); option:`symbol$(); path:(); content:())
toolreqs: ([] torch:`symbol$(); option:`symbol$(); tool:`symbol$(); probe:(); install:())
provides: ([] torch:`symbol$(); option:`symbol$(); capability:`symbol$())
requires: ([] torch:`symbol$(); capability:`symbol$())
edges:    ([] src:`symbol$(); label:`symbol$(); dst:`symbol$())
```

### Finding torches by meaning

`embed` turns text into a small bag-of-words vector via the hashing trick; `nearest[text;n]` ranks torches by cosine similarity to a query. This lets a torch be found by what it's *for* rather than by knowing its id — relevant to the dynamo, which needs to check whether a torch it is about to mint already exists in some form.

It is deliberately crude. It is not a semantic embedding model and does not need to be; it is a cheap first-pass filter over a set of torches whose rites are one or two sentences each.

## Invariants

Things that must remain true. A change that breaks one of these is a bug regardless of what it enables.

1. **The engine never interprets a torch.** It dispatches on `kind` and nothing else. Any behaviour specific to a particular torch lives in that torch's data.
2. **A model's return value is validated against the torch's contract before it is acted on.** A decision torch's answer must be one of the options offered.
3. **A validation torch's outcome is derived from what its check actually returned.** It is never supplied by a caller, a model, or a person clicking a button.
4. **Capability gating is applied at offer time, not at execution time.** A torch whose requirements are unmet is never presented as a live option.
5. **Extension is new rows, not new engine code.**
