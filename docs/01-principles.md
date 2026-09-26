# 01 — Principles

These are the commitments everything else has to answer to. If a proposed feature violates one of these, the feature is wrong, not the principle.

## 1. Three kinds of work, and only one of them needs a model

**Law.** Given the inputs, the output is forced. A module added to the tree implies its registration. A source file implies the path of its test. A signature implies its imports. There is no judgment and no second correct answer. This is a job for code.

**Choice.** More than one legal outcome, but the set is finite and can be written down. Which of the three existing utilities does this call? Which shape does the return take? The framework produces the menu; something else picks from it.

**Invention.** Genuinely open, with no enumerable set to choose from. The only place a language model does work nothing else could do — and far rarer than current tooling assumes.

The whole design follows from the claim that these are wildly unequal in size, and that conventional harnesses fail by treating all three as the same undifferentiated "figure it out."

## 2. The framework is the engine; the model is an oracle

In a conventional harness the model drives and the structure is advisory. Here it is inverted.

The framework walks the determined parts itself, deterministically. It halts when it reaches a torch it cannot resolve alone. At that torch it states the question, the legal answers, and the shape a valid response must take. A model answers. The framework validates that answer against the torch's contract and continues.

The model is called as a pure function at named points. It never holds a pointer into the graph.

### Why that matters structurally

This is what makes "the model can't leave the structure" true by construction rather than by instruction. There is no prompt telling the model to stay in bounds. There is simply no channel through which it could leave: it is handed one torch's contract in isolation and its return value is read, validated, and discarded. The harness is the only thing that ever moves the current position.

A system that asks the model nicely to stay inside the lines has a jailbreak surface. This one has no lines to cross.

## 3. A torch is sized to one unambiguous action

We don't have model power to spend. We have unmetered local time. That trade is deliberate: accept however many extra hops it takes in exchange for each hop being close to certain.

A torch is not a phase of work. It is the smallest single action with an unambiguous outcome:

- "Install Docker" — a torch.
- "Add argument parsing to this script" — a torch.
- "Build the backend" — not a torch. That's dozens.

**The test:** if describing what a torch does takes a paragraph, it isn't one torch.

The extra hops cost nothing but machine time. A torch sized too large costs the whole run, because the model is back to guessing at something under-specified with no way for the harness to tell a good answer from a bad one.

## 4. Rigid core, open scope

Rigidity is not narrowness. A type system is rigid and expresses unbounded programs. The constraint is on *form*, never on reach.

Extension happens by declaring new normal forms and new torches — never by loosening the structure to accommodate an awkward case. When something cannot be expressed, the answer is a new form, not an escape hatch.

**The moment the framework grows a "just do whatever here" path, it has become every other harness.** This is the principle most at risk from the ambitious parts of this design (the dynamo, evolution mode), and the one those mechanisms are specifically built to respect: they produce *more structure*, through the same gates as everything else, rather than bypassing structure.

## 5. Every model invocation is a debt

Not an achievement. A call to a model is a place the system could not resolve something itself.

This is why the ratchet exists (see [04](04-the-lineage.md) and the README). When the same torch returns the same answer time after time, that was law wearing a costume. Encode it and the torch closes permanently.

The number of points where a model is consulted should *shrink* as the system matures. Reliability and cost improve with age. This is the opposite of prompt-based scaffolding, which only ever accretes.

## 6. Most of this is engineering, not invention

There are already ten thousand tools that solve the piece you're stuck on. The real work is picking the right one and wiring it in correctly. That is where the creative choice actually lives — which tool, which library, which pattern — not in writing something novel from nothing.

Once the framework centralises that decision-making, the model behind any given torch is just a setting. Route hard torches to a bigger model, leave a local one on the easy ones, change your mind later without touching the structure.

## 7. Why local models are the target, not a compromise

A 20B model on a desktop GPU cannot hold an under-specified problem steady across a long agentic run. It can pick correctly from four options when the options are in front of it and the question is one sentence.

Small models rarely fail because they cannot reason. They fail because they are asked to reason about everything at once, with no way for the harness to distinguish a good answer from a bad one. Narrow the question and the gap to a frontier model narrows with it. At many torches it closes completely.

And a local model has an edge nothing metered can match: it runs for free, as long as you like. Held to a tight enough standard, it can spend far more structured effort per problem than you would ever pay a cloud model for — closing the gap not by being smarter, but by being patient.

That patience is the resource the entire rest of this design spends.
