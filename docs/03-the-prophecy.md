# 03 — The prophecy

One complete run through the graph, from the invocation that opens it to the last fire going out. In the biological frame ([04](04-the-lineage.md)) a prophecy is the cell, and everything in this document is happening inside it.

## The invocation

A prophecy starts with a prompt. That prompt is **the invocation**, and it is never spent.

Every subsequent model call for the rest of that prophecy has the invocation read back into it, unchanged, alongside whatever the current torch needs. No matter how many torches deep the walk has gone, the model is still answering toward the original ask — not a paraphrase of a paraphrase four steps removed.

This is the cheapest available defence against drift, and it is why the invocation is stored on the prophecy rather than passed along the walk.

## The fire

**The fire** is a position in the graph, actively walking. One thread of execution.

A prophecy is not one thread. Several fires may burn at once — because the graph has multiple disconnected roots, or because a model lit more than one option from the same position. A prophecy is however many fires happen to be burning, converging, dying, or spreading, all under the same invocation.

The prophecy dies when the last fire goes out. That is a normal ending, not a failure.

## The frontier

The set of torches currently available to light.

It starts as the graph's root torches — those with no incoming edge. After each lighting it loses the torch just lit and gains whatever that torch walkably leads to. "Walkably" is doing work there: raw edges, filtered by capability ([02](02-the-graph.md)).

Several entries at once is the normal case, not an edge case. That's what makes multiple simultaneous fires possible.

**A torch not in the frontier cannot be lit.** This is enforced in the engine, not in the UI. Attempting it is an error, not a silently-accepted request.

## Lighting a torch

What actually happens, in order:

1. **Ensure** — for each tool this torch requires under the chosen option, run its probe. If the probe fails, run the install command. Report `present`, `installed`, or `failed` per tool. A failed install is reported, not fatal, and not silently swallowed.
2. **Materialize** — write this torch's files for the chosen option into the working directory, creating parent directories as needed.
3. **Run** — if the torch has a `code` script, run it in the working directory.
4. **Resolve the option** — for a validation torch, *this is where the real option is determined*, from whether the code actually succeeded. For every other kind, the option is the one that was chosen going in.
5. **Advance** — walk the resolved option's edges, filter by capability, and update the frontier.

Step 4 is the one that is easy to get wrong and was in fact wrong at one point in this codebase. A validation torch's `pass`/`fail` is not a choice anyone gets to make — not a model, not a person clicking a node. It is the outcome of running the check. The engine overrides whatever option a caller passed in, and logs the real one.

### Shell execution

Commands run through a helper that:

- traps non-zero exits and returns `(success; output)` rather than raising, because a probe that *should* fail when a tool is missing is a normal control-flow event, not an exception
- changes directory as its own step and restores the original afterwards

The second point is not incidental. `system "cd X && Y"` is unreliable in kdb+, which special-cases any command beginning with `cd ` into changing its own process directory. Without the restore, a single torch would permanently redirect every subsequent relative path in the session.

## Context: what a model actually receives

At a decision torch, the model gets the torch's rite — and nothing else would be enough. A rite alone carries no memory of what has already happened in this run, and no picture of what exists on disk.

So a model call also receives **the brief**:

- **the invocation** — the original ask, verbatim
- **the rite** — this torch's own question
- **the chronicle** — every torch lit so far in this prophecy, in order, with the option taken
- **capabilities** — what earlier choices have granted
- **the tree** — a plain recursive listing of the working directory as it stands right now

The tree is what lets a torch make placement decisions. "Where does this new script belong" is answerable if you can see the shape of the codebase and unanswerable if you can't.

The chronicle entries are deliberately terse — torch id and option taken, not a transcript. The model does not need to re-read its own reasoning from four torches ago; it needs to know what was decided.

## The chronicle

An ordered, timestamped record of every torch lit in a prophecy with the option resolved for it. It is the prophecy's history, and it is what `brief` reads to build the trail.

Because validation outcomes are resolved rather than chosen, the chronicle is an honest record of what happened, not of what was requested.

## What a prophecy leaves behind

A working directory containing whatever its action torches wrote and its code steps produced. Under the biological frame this is the waste product — useful, worth collecting, but not the measure of the system's health. See [04](04-the-lineage.md).

## Current API

Implemented in `q/torches.q`:

| Function | Purpose |
|----------|---------|
| `begin[pid;invocation;dest]` | Open a prophecy: pin its invocation and working directory, seed the frontier with the graph's roots. |
| `light[tid;opt;dest]` | Carry out one torch. Ensure, materialize, run, resolve, report. Prophecy-agnostic. |
| `lightin[pid;tid;opt]` | Light a torch *inside* a prophecy: enforce the frontier, log to the chronicle, update the frontier. |
| `walk[frm;lbl]` | Raw edge lookup. What this option points at. |
| `walkable[pid;tid;opt]` | The same, filtered by what this prophecy's capabilities actually permit. |
| `capabilities[pid]` | Everything granted by choices made so far. |
| `state[pid]` | Full snapshot: invocation, dest, frontier, chronicle, capabilities, tree. |
| `brief[pid;tid]` / `briefText[pid;tid]` | The context bundle for a model call, structured or rendered. |
| `roots[]` | Torches with no incoming edge. The starting frontier. |
