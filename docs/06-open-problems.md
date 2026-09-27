# 06 — Open problems

## Closed since this was written

Recorded here rather than deleted, because what a problem turned out to be is
usually more useful than the fact that it is gone.

- **The library was too small to build an application.** It was 12 torches and
  one arrangement — "add a Python subcommand" — so a week-long run would have
  produced a CLI with a thousand subcommands rather than an app. Now 46 torches
  in 8 graphs, 30 of which consult no model at all. See
  [07](07-implementation.md).
- **The brief grew without bound.** It handed the model every file in the
  working directory, which with a real scaffold is tens of thousands of tokens
  of machinery the model must never touch. Now the scaffold is excluded
  (derived from the `files` table), binaries are excluded by a text allowlist,
  and `SRCCAP` caps the *total*. Measured at 8.4k characters at a kindling
  torch in a five-generation run, and it does not grow with the scaffold.
- **Capabilities died with their prophecy.** A choice made at generation 1 was
  invisible at generation 2, so every daughter re-decided what the lineage had
  already settled — precisely what the ratchet exists to prevent. Capabilities
  are now read from the whole ancestry.
- **A daughter could not walk a different graph.** The agent passed the same
  graph through forever. The kindling torch's options are now the graph ids.


Things that are genuinely unsolved. Written down as problems rather than smoothed over, so that nobody — including us later — mistakes a gap for a decision.

Ordered roughly by how badly they block what comes next.

---

## 0. Resolved since this was written

**Quadratic authoring cost.** Every generation used to re-emit the whole
program, so cost grew each generation and a run truncated mid-file at
around 160 lines. Features are now separate modules discovered by a
stable dispatcher: each generation writes one small file and touches
nothing else. Measured across five generations: 640, 267, 502, 1177,
1075 bytes — flat, against 1600/3000/4500/5700-then-truncated before.

**Validation that validated nothing.** `verify.cli` checked that
`python3 cli.py --help` exited 0, which is true of a file that only
defines functions and never calls `main()` — exactly what a truncated
generation produces. There are now three gates: the code must compile
before it is written at all, the program must emit real usage text, and
it must survive being run with actual arguments.

**Nothing could tell a good feature from a running one.** Each
generation now writes a test for its own feature against a fixed
fixture, and `test.suite` runs every test written so far. A later
generation that breaks an earlier feature fails rather than passing
because its own subcommand happens to work. This is the first thing in
the system that measures quality rather than liveness — and it is a
partial answer to problem 1 below, arrived at by choosing a domain where
correctness is checkable rather than by inventing a metric.

## 1. The fitness function

**Blocks:** [evolution mode](05-evolution.md), entirely.

Candidate selection rests on picking "the most effective" variant, and nothing here can currently make that comparison. Biology's fitness signal is brutally simple — did it reproduce — and is measured by an environment that doesn't care about intentions. "Is this generated application better" has no such referee.

Candidate signals, each partial:

| Signal | Problem with it |
|--------|-----------------|
| Validation torches passed | Measures whether the graph's own checks ran, not whether the result is good. A graph that checks little scores well. |
| Tests green | Only as good as tests nothing has verified. Trivially gamed by writing weak tests. |
| Wall-clock to completion | Rewards doing less. |
| Code size | Rewards terseness, which is not quality. |
| Whether the *next* generation could build on it without rework | The most meaningful signal available, and only measurable a full generation late. |

That last one is interesting enough to name as a direction rather than dismiss: fitness evaluated retrospectively, one generation behind, which is much closer to how biological fitness actually works — you don't know an organism was fit until its descendants exist. It costs a generation of latency and makes selection a delayed reward problem rather than an immediate comparison.

**Until this is solved, evolution mode cannot be more than a sketch.**

## 2. Governance of self-invocation

**Blocks:** the system being continuous at all, which is the condition it currently fails.

A dynamo is bounded by its validation gate: nothing enters the graph without passing. A metabolism has no equivalent. Once a kindling torch can produce the next invocation, the loop closes and the process no longer needs a person — which is the goal and also the entire risk.

Unanswered:

- What decides that a hearth may feed itself again, versus stopping and waiting?
- Does a newly minted torch require human sign-off before it is trusted in a real run, or is passing its own validation torch sufficient? (This is a trust decision, not an engineering one.)
- What is the stopping condition? A lineage with no terminating criterion runs until something external kills it.
- What resource ceiling applies — wall clock, disk, generations, token budget — and who enforces it?
- Kindling proposals are checked against the ember. What checks the ember?

The honest position: **this must be solved before the loop is closed, not after.** A running self-invoking hearth with no governance is not an experiment, it is an incident.

## 3. Model-authored code executes on the host

**Blocks:** safely running anything beyond the toy graph.

Action torches run `code` and install tools with the privileges of whoever started the process. Today those scripts are human-authored. Under the dynamo they are model-authored, and under evolution mode they are model-authored *and* auto-selected with no human in the path.

The sandbox described for candidate races is about isolation between candidates. It is not a security boundary, and the current implementation has nothing that is.

At minimum this needs a real containment story — containers, an unprivileged user, a filesystem jail — before the dynamo is turned on in anger. Related: `install` commands in `toolreqs` are arbitrary shell (the seeded Docker one pipes a remote script into a shell), which is normal practice and also exactly the thing you would not want a model composing unsupervised.

## 4. Brownfield versus greenfield

**Blocks:** the shape of the library.

When a daughter prophecy builds on its parent's work, does it:

- **extend the parent's working directory in place** — every torch written assuming an existing codebase, no separate integration step, or
- **build in a fresh directory and integrate across a boundary** — separate integration graphs wiring the new thing to the old?

Partly resolved: this should be a **choice**, not an architectural constant — a decision torch offering both, with the library carrying torches that service each path. That keeps it inside the law/choice/invention frame rather than hardcoding a preference.

Still open: whether "integration" survives as a distinct category of graph, or whether every torch should simply be written brownfield, which collapses the distinction and arguably simplifies the whole library.

## 5. Promotion back to the canonical library

**Blocks:** hearths ever improving each other.

A hearth's mutations stay in its local library. Every hearth therefore re-derives the same lessons from scratch, and the main library never gets better no matter how much compute has been spent discovering things.

Promotion is the fix and the risk: it is the point where one experiment's drift becomes everyone's baseline. If it happens it plausibly needs the dynamo's validation gate *plus* a human, and some notion of how much evidence a mutation needs before it graduates.

## 6. Generational drift

**Blocks:** long-running hearths being trustworthy.

With an imperfect fitness signal and many generations of local mutation, nothing stops a library wandering somewhere incoherent — each step defensible, the trajectory not. Biology has stabilising selection pulling toward the middle. This has nothing equivalent.

Possible directions, none designed: periodic revalidation of the whole local library against a fixed suite, a diff budget against the canonical library, or mandatory periodic re-forking from canonical.

## 7. Failure routing is still a stub

**Blocks:** nothing immediately, but it's a known lie in the current implementation.

[02](02-the-graph.md) specifies that a validation torch has a separate `fail` edge per class of failure, each landing on a torch built for that specific problem. The implementation currently has one `fail` edge that ends the prophecy — the fire dies.

That was always described as a placeholder. It becomes load-bearing the moment prophecies run unattended, because a lineage that dies on first failure never reaches a kindling site.

## 8. Cost compounding

**Blocks:** evolution mode at any real scale.

`N candidates × M kindling sites` per generation, all but `M` discarded, every generation, forever. Ten sandboxed runs to advance one step is plausible on an idle desktop and not plausible at any larger scale.

No mechanism currently exists for adaptive `N` (fewer candidates when the model is confident), for early termination of clearly-losing candidates, or for reusing work across candidates that share a prefix.

## The one that matters most

Nothing in this system judges whether the code it produces is any *good*.

Every gate asks "does it run". `verify.compile` asks whether it parses,
`verify.api` whether the routes answer, `test.suite` whether the model's own
test agrees with the model's own feature. A feature that runs, is tested by a
test that passes, and is completely useless gets through all of it — and a
lineage can spend forty generations accumulating useless features while every
check stays green.

The library makes this *sharper* rather than softer, because it can now build
much more per generation. A bigger vocabulary means more ways to be
confidently wrong.

`g.harden` is a partial answer and worth naming as one: a generation that adds
no behaviour and only improves what exists cannot add a useless feature. But
choosing to spend a generation that way is still the model's call, and nothing
forces it.
