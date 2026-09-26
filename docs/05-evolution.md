# 05 — Evolution

Off by default. A switch set once, at the founding invocation, and inherited by every prophecy descended from it.

```
evolution = false   # the hearth walks the main library directly
evolution = true    # the hearth forks its own library and breeds it
```

## Why the obvious version doesn't work

The first form of this idea was simpler: encode a low probability that a random torch gets inserted into a graph. Mutation, in the plainest sense.

It doesn't work, and the reason is worth keeping written down so nobody re-proposes it.

**Mutation without selection isn't evolution, it's noise.** Biology's mutation rate only produces adaptation because it runs against a population large enough that bad variants are discarded faster than they accumulate and good ones out-reproduce everything else. A single lineage — one prophecy kindling one daughter, kindling one daughter — has no population for selection to act across. A random torch either breaks that lineage or it doesn't; nothing is comparing it against a sibling that didn't get the mutation, so nothing could ever prefer the lucky outcome. You'd be injecting occasional unrecoverable failure with no compensating upside.

And even in the lucky case, there's no path from *this one lineage got lucky* to *the library now knows something it didn't*.

Three things were missing: something to compare against, something to measure, and a way for a winner to become permanent.

## The mechanism

What follows supplies all three.

### 1. The hearth forks the library

When `evolution = true`, the hearth copies the main library and works against its own local copy from then on. Mutations land there. The canonical library is not touched by a running hearth.

This is the containment boundary. An experiment that degrades into nonsense degrades its own library, not everyone's.

### 2. A kindling site produces candidates, not a daughter

Instead of one daughter prophecy, the kindling torch produces **N candidates** (default 5). Each starts from the same graph out of the library. Each carries a different mutation of it.

### 3. The mutations are proposed, not random

This is the pivot that makes the whole thing viable.

The variants are not random insertions. They are **N versions the model itself proposed as improvements to the graph it selected** — each one a hypothesis about how this graph could do its job better, expressed as an actual modification to the graph in the normal schema.

That changes the statistics entirely. Random mutation needs population scale and deep time because almost every variant is harmful. Proposed variation is already filtered through whatever the model knows: most candidates will be plausible, some will be genuinely better, and the failures are informative rather than merely destructive. This is directed breeding, not cosmic rays.

It also means each variant is legible. A random torch is an unexplained artefact. A proposed variant has a reason attached, which matters when a human eventually reviews what the hearth has been doing.

### 4. Candidates race in isolation

The kindling torch provisions an isolated test environment as part of its own work — setting up the sandbox is the torch's job, not an external precondition.

Each candidate graph runs there. Isolation is what makes this safe to do N times in parallel: candidates cannot see or corrupt each other, and none of them touches the parent's working directory.

### 5. The most effective candidate is selected

One winner. It becomes the daughter prophecy that actually proceeds. The losers are discarded along with their sandboxes.

The winning mutation persists in the hearth's local library, so it is inherited by everything downstream. That is the heredity step — the thing that turns a lucky variant into permanent structure.

### 6. This happens at every kindling site

Kindling sites may appear at several points in a graph. Each one runs its own race. **A single prophecy may therefore give rise to many daughters**, each the winner of its own local competition.

## The shape of a generation

```
                    parent prophecy
                          |
        +-----------------+-----------------+
        |                                   |
   kindling site A                    kindling site B
        |                                   |
   5 candidates                        5 candidates
   (proposed graph variants)           (proposed graph variants)
        |                                   |
   sandboxed race                      sandboxed race
        |                                   |
   winner -> daughter A                winner -> daughter B
        |                                   |
   (each carrying its winning mutation into the hearth's library)
```

## What this costs

Worth stating plainly, because it compounds and the bill is paid in the one resource this project claims is free.

Per generation: `N candidates × M kindling sites` full sandboxed runs, of which all but `M` are thrown away. With the defaults sketched here and two kindling sites, that is ten runs to advance one generation, eight of them discarded.

The project's core bet is that local compute is unmetered and patience is the resource to spend ([01](01-principles.md)). Evolution mode is the point where that bet gets tested hardest: it is the difference between a walk that takes an afternoon and one that takes a week. That is not automatically wrong — it is exactly the trade the project is built on — but it is the reason this is a switch and not the default.

## What is still unresolved

These are real gaps, not details to be filled in later by implementation.

**What "most effective" means.** The entire mechanism rests on a comparison it cannot currently make. Candidate selection needs a fitness signal, and "quality of a generated application" is not crisply measurable the way "did the organism reproduce" is. Candidate measures — validation torches passed, tests green, wall-clock to completion, code size, whether a *subsequent* generation could build on it without rework — are each partial and each gameable. This is the hardest open problem in the design; see [06](06-open-problems.md).

**Whether winners ever return to the main library.** A hearth's improvements currently stay local forever, which means every hearth re-derives the same lessons and the canonical library never gets better. Promoting a proven mutation back to the main library is the obvious fix and the obvious risk — it is the point where one experiment's drift becomes everybody's. If it happens at all it should require the same validation gate as the dynamo, plus plausibly a human.

**Drift.** Over many generations of local-library mutation with an imperfect fitness signal, nothing currently prevents a hearth's library from wandering somewhere incoherent. Biology has stabilising selection; this has nothing equivalent.

**What the sandbox actually runs.** A full daughter prophecy per candidate is the honest comparison and the expensive one. A cheap smoke test is affordable and may measure the wrong thing entirely.
