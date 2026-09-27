# 04 — The lineage

A single prophecy is a finite thing: it opens, it burns, it dies. This document is about what happens across many of them, and why the biological comparison is meant literally rather than decoratively.

## The frame

| Biology | Here |
|---------|------|
| The cell | A **prophecy** |
| Transcription and translation — polymerase reading along the genome, ribosomes building proteins | **Fires** walking torches and producing code |
| The genome | The **graph** the prophecy is walking |
| Cell death when its processes run down | The prophecy ending when the last fire goes out |
| Reproduction | A **kindling torch** producing a daughter prophecy |
| Heredity | The graph surviving intact into the daughter |
| Mutation | The [dynamo](#the-dynamo-versus-kindling) minting torches; [evolution mode](05-evolution.md) proposing graph variants |
| Metabolism | Compute in, structured work out, code as waste |

The important correction, easy to get backwards: **a fire is not a cell dividing.** A fire is machinery *inside* the cell. Several fires burning at once is one cell with a lot going on internally — many ribosomes working in parallel — not several organisms. Reproduction is a separate, deliberate event, and it is what the rest of this document is about.

## Metabolism, and code as waste

Unmetered local compute goes in. Structured torch-walks come out. That is the metabolism, and it is already the whole premise of the project ([01](01-principles.md)).

The reframe worth sitting with is what comes out the other end. **The code and applications left behind by a run are not the point of the system — they are its waste product.** Useful waste, the kind worth collecting, but waste all the same.

This changes what "working" means. A run that produces mediocre code but leaves the process healthy and able to continue matters more than one that produces a single excellent app and then stops. Judge the metabolism, not any one excretion.

It also suggests the waste is not inert: a daughter prophecy reading the parent's output as its starting context is the system consuming its own byproduct as feedstock for the next cycle.

## The ember

The founding invocation — the one that started the whole lineage, before any daughter existed.

An individual prophecy's invocation is local and disposable; it dies with that prophecy. The ember persists across every death in the lineage. It is the thing a kindling proposal can be checked against: *does building humidity support still serve the ember?* is a real, askable question, and without a named founding intent it is not.

**(Name proposed, not settled.)**

## The hearth

The entire multi-generational process: one ember, one library, and every prophecy descended from the first.

The hearth is what is actually alive. Individual prophecies are its cells — born, productive, dead. Under [evolution mode](05-evolution.md), the hearth is also the scope of a library fork: it holds its own mutable copy of the graph library, distinct from the canonical one.

**(Name proposed, not settled.)**

## Kindling

At a mature point in a prophecy — after the work has been built and validated, not before — a **kindling torch** looks back at what actually got made and produces the invocation for the next prophecy.

What it receives:

- **the ember** — what this whole lineage is ultimately for
- **this prophecy's invocation** — what this particular cell was for
- **the chronicle and the tree** — what was actually built, and what state it left behind

What it produces: two things, both narrow.

1. **Which arrangement the daughter walks.** The kindling torch's `options`
   *are* the library's graph ids, so the menu is the library index and cannot
   drift out of step with it. The menu is then narrowed by `offerable` — the
   graphs whose root torch this lineage's inherited capabilities permit — so a
   lineage that chose JSON storage is never offered the schema graph.
2. **The invocation** the daughter carries, in one sentence.

That is the entire executive call, and it is deliberately as rigid as every
other torch in the library. The model does not choose where the daughter
works, what torches exist, how they are wired, or whether its own output was
acceptable. The overview it answers from is `SURVEY.txt`, derived from the code
by a script — so even the context for this call is law rather than narration.

The worked example: a prophecy builds a rainfall app. Near its end, a kindling torch observes what exists, checks it against the ember, and proposes *also fetch humidity*. That becomes a daughter prophecy, which selects the graphs it needs — an API graph, an internet-access graph, a database graph, whatever integration the existing codebase requires — and builds.

An observed run of exactly this shape, five generations, entirely unattended:
`g.found` installs the project and chooses sqlite and both surfaces;
`g.feature` adds a subcommand; `g.schema` adds a table via a migration that
sqlite applies and the checker reads back; `g.harden` spends a whole
generation on seven deterministic checks and **no authoring calls at all**;
`g.document` regenerates the docs and declines to continue. Each generation
left a git commit and a fresh `SURVEY.txt` for the next one to read.

### Several kindling sites

A prophecy is not limited to one kindling torch, and kindling is not limited to the very end of a walk. Kindling sites may appear at several places in a graph, so **one prophecy may give rise to many daughters**, each pursuing a different direction implied by what was built.

That is what turns a chain into a lineage tree, and it is also where the cost question gets sharp — see [06](06-open-problems.md).

## The dynamo versus kindling

Two mechanisms that are easy to conflate and shouldn't be. They answer different questions.

| | The dynamo | Kindling |
|---|---|---|
| Question | "What torch do we need that doesn't exist?" | "What should we build next?" |
| Changes | The graph — adds new torches | Nothing structural; spawns a new prophecy |
| Biological analogue | Mutation, new genes | Reproduction, heredity |
| Gate | A validation torch dry-runs the proposal before it's admitted | The daughter is just a prophecy; it validates as it walks |

They compose. Kindling decides *what's next*; the dynamo supplies *whatever doesn't exist yet* to get there. A daughter prophecy pursuing humidity may find the library has no torch for the API it needs, and the dynamo mints one — which must pass the same validation gate as any other torch before it becomes real.

### Keeping the dynamo honest

A graph that grows itself is, done carelessly, exactly the "just do whatever here" escape hatch principle 4 forbids. It is admissible only because torch-creation is made into a normal form rather than a backdoor:

- A **torch-authoring torch** is an ordinary torch. It proposes a new torch's rite, code, files, and tool requirements in the same schema everything else uses. It does not get to skip the form, only to produce more of it.
- Nothing it proposes enters the live graph on its own say-so. A validation torch dry-runs the proposal, sandboxed, against synthetic input.
- A proposal that fails validation dies, like any other failed torch.

The graph never grows because a model asserted something. It grows because something passed the same gate everything else passes.

### The ratchet's second direction

The ratchet consolidates inward: a torch that keeps returning the same answer collapses into law, and the graph gets smaller and more certain over time.

The dynamo runs outward: when raw invention at some torch keeps recurring in a similar shape across prophecies, that recurrence is the signal to mint a torch and formalise it — shrinking how often real invention is needed next time.

Same instinct, two directions: **turn whatever repeats into structure**, whichever way the repetition is found.

## What makes it alive, and what doesn't yet

Against the four conditions:

- **Metabolizing** — yes. Compute in, work out, waste behind.
- **Self-replicating** — yes, via kindling. Implemented.
- **Continuous / self-sustaining** — implemented, and deliberately fenced. The
  agent runs generation after generation with no human input and no generation
  counter; what stops it is the model declining, a disk cap, a prophecy
  ceiling, or a `HALT` file appearing. `kindle` refuses rather than warns when
  one is hit.
- **Heritable** — yes, and across generations rather than within one. A choice
  made by the founding prophecy still gates which torches the fortieth
  generation is offered, because capabilities are read from the whole ancestry
  rather than one prophecy's chronicle.

And the honest warning, which belongs here rather than buried in a footnote: **a dynamo is bounded by its validation gate; a metabolism with no check on whether it may feed itself again is bounded by nothing.** The ceilings implemented today are a crude answer to that — they stop a runaway by counting, not by judging. They are enough to make the loop safe to run on a desktop and nowhere near enough to make it trustworthy at scale. What *should* decide whether a hearth has earned another generation is still open. See [06](06-open-problems.md).
