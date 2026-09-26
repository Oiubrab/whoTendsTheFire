# whoTendsTheFire — design documents

The [README](../README.md) is the argument. These documents are the specification.

Read in order if you're new:

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Principles](01-principles.md) | Law, choice, invention. Why the framework is the engine and the model is an oracle. How small a torch should be. |
| 02 | [The graph](02-the-graph.md) | Torches, edges, capabilities, the library of graphs. The data model. |
| 03 | [The prophecy](03-the-prophecy.md) | One run, end to end. Invocation, fire, frontier, context, the execution contract. |
| 04 | [The lineage](04-the-lineage.md) | Hearth, ember, kindling, daughter prophecies. The biological frame taken literally. |
| 05 | [Evolution](05-evolution.md) | `evolution = true`: local library forks, competing variants, sandboxed selection. |
| 06 | [Open problems](06-open-problems.md) | What is genuinely unsolved, stated honestly rather than hand-waved. |
| 07 | [Implementation](07-implementation.md) | What actually exists and runs today, and how to run it. |

## A note on names

This project has coined a lot of vocabulary. That is deliberate: the concepts don't map cleanly onto existing software words, and borrowing a word like "node" or "job" or "agent" drags in assumptions that are wrong here. But it does mean the glossary is load-bearing. When a document uses one of these words, it means the specific thing defined below, not a loose synonym.

Names marked **(proposed)** are not settled and are waiting on a decision.

## Glossary

### Structure

**Torch** — a node in the graph. The smallest unit of work with a single unambiguous outcome. "Install Docker" is a torch. "Build the backend" is not; that's several.

**Decision torch** — offers the model a finite, enumerated set of options and takes back exactly one. Returns a choice, never prose.

**Action torch** — runs deterministic code. Writes files, runs installs, executes a build step. No model involved.

**Validation torch** — runs a check and branches on the result. Its outcome is determined by what the check actually returned, never by anyone's choice.

**Rite** — the prompt attached to a torch, handed to the model when that torch is reached. Scoped to that torch alone.

**Option** — a labelled outgoing edge. A decision torch's options are the menu it presents; an action torch typically has one; a validation torch has `pass` and `fail`.

**Capability** — something a chosen option grants (picking a Python base image provides `python3`). Torches declare what they require; unsatisfied requirements make a torch unreachable, even when an edge points at it.

**Graph** — a named, reusable arrangement of torches for a class of work. Not the whole torch universe: one graph among many in a library.

**Library** — the collection of graphs. The **main library** is canonical and shared. A **local library** is a private copy forked by one hearth, and only exists under `evolution = true`.

### Running

**Prophecy** — one complete run, from invocation to the last fire going out. The cell.

**Invocation** — the prompt that opens one prophecy. Re-fed into every model call for that prophecy's whole life, so late decisions still answer the original ask.

**Fire** — a position in the graph, actively walking. One thread of execution. A prophecy may have several burning at once.

**Lighting** — choosing an option at a torch and executing what that choice entails.

**Frontier** — the set of torches currently available to light. More than one entry is normal.

**Chronicle** — the ordered record of every torch lit in a prophecy, with the option taken.

**Brief** — everything a model call gets beyond its own rite: the invocation, the chronicle so far, capabilities held, and the current state of the working directory.

### Lineage

**Ember** *(proposed)* — the founding invocation. The one that started the whole lineage, persisting across the death of every individual prophecy. Every kindling proposal can be checked against it.

**Hearth** *(proposed)* — the entire multi-generational process: one ember, one library (local or main), and every prophecy descended from the first. The scope a fork applies to and the thing that is actually "alive."

**Kindling torch** — a torch near the end of a mature prophecy whose job is to produce the invocation for the next one.

**Daughter prophecy** — a prophecy produced by a kindling torch. A single prophecy may have several, from several kindling sites.

### Mechanisms

**The ratchet** — consolidating inward. When a torch keeps returning the same answer, that was law in disguise; encode it and the torch closes forever. The set of points needing a model shrinks as the system matures.

**The dynamo** — expanding outward. Minting new torches, in the same schema as every other torch, admitted to the graph only after passing a validation gate.

**Evolution mode** — at a kindling site, producing several competing variants of a graph rather than one daughter, racing them in isolation, and keeping the winner. Off by default.
