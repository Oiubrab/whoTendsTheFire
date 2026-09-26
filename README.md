# whoTendsTheFire

An LLM harness built on the premise that most of software development is not creative work, and should stop being handed to a model as though it were.

*This document is the argument. The specification lives in [docs/](docs/00-index.md) — including a glossary, since this project coins a lot of vocabulary, and an honest [list of what's still unsolved](docs/06-open-problems.md).*

## The premise

Walk outside and you are obeying physical law — gravity, friction, the mechanics of your own joints. You are also choosing: the path or the grass, this stride or the next. And once in a long while you do something genuinely inventive; you walk on your hands.

Three layers, and they are nothing like equal in size. The overwhelming majority of crossing a field is determined. A smaller part is selection among legal options. A vanishing sliver is invention.

Development is the same, and we keep building tools that pretend otherwise.

## The problem with "just figure it out"

Most harnesses are a free-form code editor with a model bolted to it and an instruction that amounts to *just figure it out*. There is guidance — system prompts, style guides, tool descriptions — but no rigidity. The model is asked to rediscover the determined parts on every invocation, in prose, from scratch, and to do that in the same breath as the parts that genuinely require judgment. It arrives as one undifferentiated stream of "figure it out."

Two things follow. The model spends most of its capacity re-deriving what was never in question. And every failure looks alike: a wrong import and a wrong architecture come through the same channel, in the same format, with the same confidence.

## Three kinds of work

**Law.** Given the inputs, the output is forced. A module added to the tree implies its registration. A source file implies the path of its test. A signature implies its imports. There is no judgment here and no second correct answer. This is not a job for a model; it is a job for code.

**Choice.** More than one legal outcome, but the set is finite and can be written down. Which of the three existing utilities does this call? Which of these shapes does the return take? The framework's job is to produce the menu. Something else's job is to pick from it.

**Invention.** Genuinely open, with no enumerable set to choose from. This is the only place a language model does work that nothing else could do — and it is far rarer than current tooling assumes.

## The inversion

In a conventional harness the model is the engine and the structure is advisory. Here it is the other way around.

The framework is the engine. It walks the determined parts itself, deterministically, and it halts when it reaches a point it cannot get past on its own. At that point it states the question, the legal answers, and the shape a valid response must take. A model answers. The framework validates that answer against the point's contract and carries on. (This point has a name — see [The shape: a graph](#the-shape-a-graph) below.)

The model is an oracle consulted at named points, not a driver holding the wheel.

## Why this makes local models viable

A 20B model on a desktop GPU cannot hold an under-specified problem steady across a long agentic run. It can pick correctly from four options when the options are in front of it and the question is one sentence.

Small models rarely fail in conventional harnesses because they cannot reason. They fail because they are asked to reason about everything at once, with no way for the harness to distinguish a good answer from a bad one. Narrow the question and the gap between a local model and a frontier model narrows with it. At many of these points it closes completely.

Most of this is not invention anyway. It is engineering: there are already ten thousand tools out there that solve the piece you're stuck on, and the real work is picking the right one and wiring it in correctly. That's where the creative choice actually lives — which tool, which library, which pattern, not writing something novel from nothing. Once the framework is doing that centralizing — deciding what to use and where — the model behind any given point is just a setting. Swap in a bigger model for the hard points, leave a local one on the easy ones, change it later without touching anything else.

And a local model has a real edge here: it runs on your own machine for free, as long as you like, with no meter running. If the framework holds it to a tight enough standard, that local model can spend far more time and far more structured effort per problem than you'd ever pay for from a cloud model — closing the gap not by being smarter, but by being patient.

This settles how small a torch should actually be. We don't have model power to spend, but we have unmetered time, so the trade is deliberate: accept however many extra hops it takes in exchange for each one being close to certain. A torch shouldn't be sized to a phase of a project — it should be sized to the smallest single action with an unambiguous outcome. "Install Docker" is a torch. "Add argument parsing to this script" is a torch. If describing one takes a paragraph, it isn't one torch, it's several. The extra hops cost nothing but machine time; a wrong guess at a torch sized too large costs the whole run.

## The shape: a graph

This is not a single abstract pause button. It is a node in a graph, and the graph is the whole system. We give the node a name in keeping with the rest of this document and call it a **torch** — it's what the framework carries forward, and it's the point of light the model is handed for one narrow moment before the framework moves on without it.

There are three kinds of torch. A **decision torch** hands the model a finite, enumerated set of options and nothing else — it returns a choice, not prose. An **action torch** takes a choice already made and runs deterministic code against it — codegen, a build step, a file write — with no model involved at all. A **validation torch** runs a check and does nothing but branch on the result.

Edges are outcomes, not arrows drawn for convenience. A decision torch has exactly one outgoing edge per option offered. A validation torch has a pass edge, and — this is the part that matters — a *separate* fail edge per class of failure, each one landing on a torch built to handle that specific problem. A wrong import and a broken architecture do not both loop back to "try again." They go to different places, because they are different problems.

The graph lives in a database, not in the engine's code. The engine's only job is to walk it: stand at a torch, gather what that torch needs, invoke a model or run deterministic code as the torch's type demands, take the result, follow the matching edge, repeat. It does not know what any torch "means." That knowledge lives entirely in the graph's data, which is what makes extension safe — a new capability is a new torch and a new edge, committed to the database, and the engine that walks the graph never has to change to accommodate it.

This is also the answer to "how does the model never leave the structure." It doesn't hold a pointer into the graph and never did. At a decision torch, the harness calls the model as a pure function — these are your options, or here is a narrow enough spec to write a small script — and reads back a choice or a small artifact. The harness is the only thing that ever moves the current position. There is no path from inside a model call back out to the graph, because the model was never given the graph to navigate — only the one torch's contract, in isolation, held out to it and then taken back.

The lifecycle stages described earlier — scaffold, implement, verify, integrate, ship — were never a separate idea from this. They are the backbone path through the graph, described before it had torches and edges. "Verify" is a validation torch. "Implement" is wherever the decision and action torches for a unit of work sit. The feature loop is a walk from one side of the graph to the other and back.

## A run: the prophecy

One full pass through the graph — from the user's first prompt to wherever the walk stops — is a **prophecy**.

It starts with the user writing a prompt. Call that prompt **the invocation**: it is what opens the whole prophecy, and it is never spent. Every subsequent model call for the rest of that prophecy has the invocation read back into it, unchanged, alongside whatever the current torch needs — so no matter how many torches deep the walk has gone, the model is still answering toward the original ask, not some drifted paraphrase of it several steps removed.

The current position in the graph is **the fire** — where we are, right now, in this prophecy. Standing at a torch, the fire is handed the invocation and that torch's offered options, and the model **lights** one: picks an edge. If the torch is an action torch, the framework writes the code or runs the install that torch specifies. The model may then be called once more, this time with the invocation plus that torch's own **rite** — a system prompt specific to that torch, covering whatever configuration or small scripting is needed to actually make the torch's work take hold. A validation torch then runs its check automatically. If it fails, the fire dies and the prophecy ends there — the simplest possible failure behavior, and a placeholder for something better once it's worth routing failures to a torch built for them instead (see "The shape: a graph," above). If it passes, the fire moves on, arriving at the next torch's offered options, the invocation still in force.

A fire is not required to stay singular. If the model lights more than one torch from the same position — chooses two or more edges instead of one — the fire splits. Each lit edge becomes its own fire, its own model call, running in parallel, walking the graph independently from that point on. A prophecy is not one thread through the graph; it's however many fires happen to be burning at once, converging, dying, or spreading, all called into being by the same invocation.

## Rigid core, open scope

Rigidity is not narrowness. A type system is rigid and expresses unbounded programs. The constraint is on *form*, never on reach.

Extension happens by declaring new normal forms and new torches — never by loosening the structure to accommodate an awkward case. When something cannot be expressed, the answer is a new form, not an escape hatch. The moment the framework grows a "just do whatever here" path, it has become every other harness.

## The ratchet

Every model invocation is a debt, not an achievement.

When the same torch returns the same answer time after time, that was law wearing a costume. Encode it and the torch closes permanently. The set of points where a model is consulted should shrink as the system matures, which means reliability and cost improve with age.

This is the opposite of prompt-based scaffolding, which only ever accretes.

## The dynamo

Everything so far describes a graph that a person authors and a model walks. The natural next step is a graph that grows itself — new torches minted while a prophecy runs, not just new choices among ones that already exist. Done carelessly this is exactly the "just figure it out" escape hatch the rest of this document argues against, so it only belongs here if torch-creation is made into a normal form rather than a backdoor.

The way to keep it honest: a **torch-authoring torch** is still an ordinary torch. It proposes a new torch's rite, code, files, and tool requirements in the same schema every other torch already uses — it does not get to skip the form, only to produce more of it. Nothing it proposes enters the live graph on its own say-so. A validation torch dry-runs the proposal — sandboxed, against synthetic input — before it's trusted, exactly like any other check in this system. A proposal that fails validation just dies, the same as any other failed torch. The graph never grows because a model asserted something; it grows because something passed the same gate everything else has to pass.

This gives the ratchet a second direction. The ratchet consolidates inward: a torch that keeps returning the same answer collapses into law, and the graph gets smaller and more certain over time. The dynamo is the mirror, running outward: when raw invention at some torch keeps recurring in a similar shape across prophecies, that recurrence is the signal to mint a new torch and formalize it — shrinking how often real invention is needed the next time it comes up. Together they are the same instinct pointed in two directions: turn whatever repeats into structure, whichever way the repetition is found.

## A living process, not a library

Scale the ambition up and a different comparison fits better than "framework" or "graph library": this looks like an attempt at artificial life, and it is worth taking that literally rather than as a flourish. A living process is continuous, self-sustaining, self-replicating, and metabolizing — and each of those has a concrete, unmetaphorical meaning here.

**Metabolizing** is already the whole premise: unmetered local compute goes in, structured torch-walks come out. The reframe worth sitting with is what comes out the other end. The code and applications left behind by a run are not the point of the system — they are its waste product. Useful waste, worth collecting, but waste all the same: judged by whether the process kept running well, not by whether any one thing it excreted was good.

The level the metaphor sits at matters, and it's easy to get backwards. **A prophecy is the cell.** The fires burning inside it are its internal machinery — polymerase reading along the genome, ribosomes building proteins — not organisms in their own right. Several fires at once is one cell with a lot going on, not several cells. The graph being walked is the genome. When the last fire goes out the prophecy dies, which is an ordinary ending rather than a failure.

**Self-replicating**, then, is a separate and deliberate event, not something a splitting fire does incidentally. At a mature point in a prophecy — after work has been built and validated — a **kindling torch** looks back at what actually got made and produces the invocation for the next prophecy. The graph survives into the daughter intact; that's heredity. A prophecy that built a rainfall app can notice what it has and propose *also fetch humidity*, and that becomes a daughter walking the same library from the start. Several kindling sites can sit in one graph, so a single prophecy may give rise to many daughters.

For that to be checkable there has to be something older than any individual prophecy's invocation to check against: **the ember**, the founding invocation the whole lineage traces back to. *Does humidity still serve the ember?* is a real question. And the whole multi-generational thing — one ember, one library, every descendant — is **the hearth**. The hearth is what's actually alive; prophecies are its cells.

**Self-sustaining and continuous** is what kindling buys, and it's the condition the system currently fails. Right now the process halts the moment a prophecy resolves and waits for a person to hand it the next invocation. A thing that metabolizes doesn't wait to be fed one meal at a time. Closing that loop is the system consuming its own waste as feedstock for the next cycle rather than a person restarting it each time.

There is an optional evolutionary mode on top of this, off by default: a hearth can fork its own copy of the graph library, have a kindling site produce several competing variants of a graph rather than one daughter, race them in isolation, and keep the winner. The variants are not random mutations — random mutation without population-scale selection is just noise — they're improvements the model itself proposed, which makes each one a hypothesis rather than damage. What it still lacks is a way to say which outcome was actually better, and that gap is load-bearing enough to be written down rather than papered over.

That last piece is also where the danger concentrates. A dynamo that can mint new structure is bounded by its validation gate. A metabolism with no check on whether it's allowed to feed itself again is not bounded by anything — it is a runaway process wearing a nicer name. Whatever decides "does this get to invoke itself once more" is the actual hard problem here, harder than torch-authoring, and it has to be solved before this stops being a metaphor.

## Status

The graph engine, a local UI, and a local-model-driven agent all exist and run end to end — a full walk from invocation to working code, decided entirely by a model running on this machine. Kindling, the dynamo, and evolution mode do not exist yet; they are the specification of intent the code has to answer to next. See [what's built versus what's described](docs/07-implementation.md).

Two things are unsolved in ways that block what comes next, and are worth naming here rather than burying: there is **no fitness signal**, so nothing can yet say which of several outcomes was better — and there is **no governance on self-invocation**, which has to be settled before the loop is closed rather than after. A metabolism with no check on whether it may feed itself again isn't bounded by anything.

---

The fire is the part that cannot be mechanized. Tending it is everything else.
