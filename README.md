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

The framework is the engine. It walks the determined parts itself, deterministically, and it halts when it reaches a seam it cannot close on its own. At that seam it states the question, the legal answers, and the shape a valid response must take. A model answers. The framework validates that answer against the seam's contract and carries on.

The model is an oracle consulted at named points, not a driver holding the wheel.

## Why this makes local models viable

A 20B model on a desktop GPU cannot hold an under-specified problem steady across a long agentic run. It can pick correctly from four options when the options are in front of it and the question is one sentence.

Small models rarely fail in conventional harnesses because they cannot reason. They fail because they are asked to reason about everything at once, with no way for the harness to distinguish a good answer from a bad one. Narrow the question and the gap between a local model and a frontier model narrows with it. At many seams it closes completely.

Because each seam declares its own question and its own contract, the model behind a seam becomes configuration. Route the bounded choices to whatever runs on the desk; route the genuine inventions to the largest model available; change your mind later without touching the structure. Rotation is a config edit, not a rewrite.

## Rigid core, open scope

Rigidity is not narrowness. A type system is rigid and expresses unbounded programs. The constraint is on *form*, never on reach.

Extension happens by declaring new normal forms and new seams — never by loosening the structure to accommodate an awkward case. When something cannot be expressed, the answer is a new form, not an escape hatch. The moment the framework grows a "just do whatever here" path, it has become every other harness.

## The ratchet

Every model invocation is a debt, not an achievement.

When the same seam returns the same answer time after time, that was law wearing a costume. Encode it and the seam closes permanently. The set of points where a model is consulted should shrink as the system matures, which means reliability and cost improve with age.

This is the opposite of prompt-based scaffolding, which only ever accretes.

## Status

Framing first. There is no implementation yet — this document is the specification of intent that the code will have to answer to.

---

The fire is the part that cannot be mechanized. Tending it is everything else.
