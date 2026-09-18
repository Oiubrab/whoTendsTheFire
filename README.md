# whoTendsTheFire

An LLM harness built on the premise that most of software development is not creative work, and should stop being handed to a model as though it were.

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

## The shape: a graph

This is not a single abstract pause button. It is a node in a graph, and the graph is the whole system. We give the node a name in keeping with the rest of this document and call it a **torch** — it's what the framework carries forward, and it's the point of light the model is handed for one narrow moment before the framework moves on without it.

There are three kinds of torch. A **decision torch** hands the model a finite, enumerated set of options and nothing else — it returns a choice, not prose. An **action torch** takes a choice already made and runs deterministic code against it — codegen, a build step, a file write — with no model involved at all. A **validation torch** runs a check and does nothing but branch on the result.

Edges are outcomes, not arrows drawn for convenience. A decision torch has exactly one outgoing edge per option offered. A validation torch has a pass edge, and — this is the part that matters — a *separate* fail edge per class of failure, each one landing on a torch built to handle that specific problem. A wrong import and a broken architecture do not both loop back to "try again." They go to different places, because they are different problems.

The graph lives in a database, not in the engine's code. The engine's only job is to walk it: stand at a torch, gather what that torch needs, invoke a model or run deterministic code as the torch's type demands, take the result, follow the matching edge, repeat. It does not know what any torch "means." That knowledge lives entirely in the graph's data, which is what makes extension safe — a new capability is a new torch and a new edge, committed to the database, and the engine that walks the graph never has to change to accommodate it.

This is also the answer to "how does the model never leave the structure." It doesn't hold a pointer into the graph and never did. At a decision torch, the harness calls the model as a pure function — these are your options, or here is a narrow enough spec to write a small script — and reads back a choice or a small artifact. The harness is the only thing that ever moves the current position. There is no path from inside a model call back out to the graph, because the model was never given the graph to navigate — only the one torch's contract, in isolation, held out to it and then taken back.

The lifecycle stages described earlier — scaffold, implement, verify, integrate, ship — were never a separate idea from this. They are the backbone path through the graph, described before it had torches and edges. "Verify" is a validation torch. "Implement" is wherever the decision and action torches for a unit of work sit. The feature loop is a walk from one side of the graph to the other and back.

## Rigid core, open scope

Rigidity is not narrowness. A type system is rigid and expresses unbounded programs. The constraint is on *form*, never on reach.

Extension happens by declaring new normal forms and new torches — never by loosening the structure to accommodate an awkward case. When something cannot be expressed, the answer is a new form, not an escape hatch. The moment the framework grows a "just do whatever here" path, it has become every other harness.

## The ratchet

Every model invocation is a debt, not an achievement.

When the same torch returns the same answer time after time, that was law wearing a costume. Encode it and the torch closes permanently. The set of points where a model is consulted should shrink as the system matures, which means reliability and cost improve with age.

This is the opposite of prompt-based scaffolding, which only ever accretes.

## Status

Framing first. There is no implementation yet — this document is the specification of intent that the code will have to answer to.

---

The fire is the part that cannot be mechanized. Tending it is everything else.
