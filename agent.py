#!/usr/bin/env python3
"""Run a hearth end to end using the local model.

A hearth is the whole multi-generational process: one ember, and every
prophecy descended from it. This walks a prophecy torch by torch, asking
torch-gpt-oss (our own gpt-oss-20b GGUF, imported into Ollama) to pick
an option at each decision, and when it reaches a kindling torch it asks
whether there is a worthwhile next thing to build -- spawning a daughter
prophecy and continuing into it if so.

The loop stops when the model declines to kindle, when the hearth runs
out of budget, or when a step ceiling is hit. It does not stop on its
own initiative, which is exactly why those ceilings exist.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import calllog

BRIDGE = "http://127.0.0.1:8420"
OLLAMA = "http://localhost:11434"
MODEL = "torch-gpt-oss"
# g.resource's clean path -- 11 emit torches plus their checks plus the
# now-two-step kindling (kindle.next, then choose.graph) -- runs right up
# against 30 with zero repairs needed, found by a real isolated run that
# hit the ceiling despite every single check passing. 45 gives a clean
# g.resource walk real headroom for the repair loops it's actually built
# to tolerate, without raising this so far that a genuinely stuck
# prophecy burns a lot more real model time before the ceiling catches it.
MAX_STEPS_PER_PROPHECY = 45
EVOLVE = False
GRAPH_EDGES = []


def http_json(url, data=None, timeout=900):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


FINAL = "<|channel|>final<|message|>"


def _extract(raw: str) -> str | None:
    """Pull the final-channel message out of a Harmony response.

    gpt-oss emits its reasoning in an `analysis` channel before the real
    answer in `final`. If the generation was cut short by the token
    budget it never reaches `final`, and what's left is raw reasoning --
    which must not be mistaken for an answer. Returns None in that case.
    """
    if FINAL in raw:
        text = raw.rsplit(FINAL, 1)[1]
        for stop in ("<|end|>", "<|return|>", "<|start|>"):
            text = text.split(stop)[0]
        text = text.strip()
        return text or None
    if "<|channel|>" in raw or "<|message|>" in raw:
        return None  # truncated mid-reasoning
    return raw.strip() or None


# The bridge honours FAKE_MODEL for authoring calls, but decisions and
# kindling are asked from here, directly of Ollama -- so without this the
# "canned model" selftest was quietly making real model calls for every
# choice it made, taking minutes instead of seconds and giving a different
# answer each run. A harness that is only deterministic in half its calls
# is not deterministic.
FAKE_MODEL = os.environ.get("FAKE_MODEL") == "1"

# Ollama's default context is 4096 tokens and it truncates from the FRONT,
# silently dropping the invocation and the ember -- the two things every
# call is supposed to be answering toward. The brief is already ~10k
# characters at a kindling torch.
NUM_CTX = int(os.environ.get("NUM_CTX", "32768"))

FAKE_CHOICES = {
    "choose.surface": "both",
    "choose.storage": "sqlite",
    "choose.license": "mit",
}
# Overridable so a canned run can be aimed at any arrangement:
#   FAKE_KINDLES=g.fullstack,g.route,g.view python3 agent.py ...
# Without this, whichever graphs the default sequence omits are never
# exercised by any fast test, which is how untested graphs ship.
FAKE_KINDLE_ORDER = [g for g in os.environ.get(
    "FAKE_KINDLES", "g.feature,g.schema,g.harden,g.document").split(",") if g]
FAKE_KINDLES = []


def fake_reply(prompt: str, torch: str | None = None) -> str:
    """Canned answers for the executive calls, keyed on the TORCH.

    Keyed on the torch id passed in, never on the prompt text. Sniffing the
    prompt looked equivalent and was not: the brief embeds the chronicle, so
    every later prompt contains "choose.surface -> both", the surface answer
    was returned for the storage question, it matched no storage option, and
    the run silently fell back to the default. The same mistake the bridge's
    canned answers already had to be fixed for.
    """
    # kindle.next and choose.graph are two separate calls now, not one --
    # the first writes the sentence and advances FAKE_KINDLES, the second
    # reads the SAME position back to answer consistently with it.
    if torch == "kindle.next":
        i = len(FAKE_KINDLES)
        FAKE_KINDLES.append(1)
        if i >= len(FAKE_KINDLE_ORDER):
            return "DECLINE"
        return "Add a way to record and report stored items."
    if torch == "choose.graph":
        i = len(FAKE_KINDLES) - 1
        if 0 <= i < len(FAKE_KINDLE_ORDER):
            want = FAKE_KINDLE_ORDER[i]
            # only offer a graph this prophecy could actually walk, so the
            # canned run exercises the capability gate rather than fighting it
            if want in prompt:
                return want
        return ""  # no usable match -- choose_graph() falls back to options[0]
    if torch and torch in FAKE_CHOICES:
        return FAKE_CHOICES[torch]
    return "done"


def ask_model(prompt: str, num_predict: int = 600,
              torch: str | None = None, pid: str | None = None) -> str | None:
    """Call the local model. None means it produced nothing usable.

    pid, when given, logs the call (prompt, reply, timing, token counts)
    to calllog for the Activity tab's inspector -- the only reason this
    function needs to know what a pid is. Every existing call site that
    doesn't pass one (there were none before Phase 3) keeps logging off.
    """
    if FAKE_MODEL:
        reply = fake_reply(prompt, torch)
        calllog.record(pid, torch, prompt, reply, 0, None, None, MODEL, True)
        return reply
    started = time.monotonic()
    for budget in (num_predict, num_predict * 3):
        res = http_json(f"{OLLAMA}/api/generate", {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": budget,
                        "num_ctx": NUM_CTX},
        })
        text = _extract(res.get("response", ""))
        if text is not None:
            calllog.record(
                pid, torch, prompt, text, round((time.monotonic() - started) * 1000),
                res.get("prompt_eval_count"), res.get("eval_count"), MODEL, False,
            )
            return text
        # ran out of budget mid-reasoning; give it more room once
    calllog.record(pid, torch, prompt, None, round((time.monotonic() - started) * 1000), None, None, MODEL, False)
    return None


def choose_option(brief_text: str, torch: dict, pid: str | None = None) -> str:
    options = torch["options"]
    if len(options) == 1:
        return options[0]
    if torch["kind"] == "validation":
        # pass/fail is resolved from what the check actually returned;
        # light[] overrides whatever we send, so asking would be theatre.
        return options[0]
    prompt = (
        f"{brief_text}\n\n"
        f"You are standing at torch '{torch['id']}' ({torch['kind']}).\n"
        + (f"Its question: {torch['rite']}\n" if torch["rite"] else "")
        + "Choose exactly one of these options and reply with ONLY that option's exact text, nothing else:\n"
        + ", ".join(options)
        + "\n\nOption:"
    )
    reply = ask_model(prompt, torch=torch["id"], pid=pid)
    if reply is None:
        print(f"      (no usable reply -- defaulting to {options[0]!r})")
        return options[0]
    lowered = reply.lower()
    for opt in options:
        if opt.lower() in lowered:
            return opt
    print(f"      (model said {reply!r}, matched no option -- defaulting to {options[0]!r})")
    return options[0]


def propose_kindling(brief_text: str, torch: dict, ember: str, pid: str | None = None) -> str | None:
    """Ask the model for the daughter's invocation -- what to build, not
    how. Returns None to decline.

    Used to also ask for a graph in the same reply (a GRAPH:/NEXT: format).
    Split apart after watching a real lineage get the sentence right five
    times running while getting the graph wrong five times running, in the
    same response: asking for a closed-menu CHOICE and an open INVENTION
    in one breath is exactly the thing docs/01's law/choice/invention split
    exists to prevent, and this was the one torch in the library doing it.
    choose_graph (below) now does the choosing, informed by the sentence
    this returns, once it already exists rather than alongside it.
    """
    prompt = (
        f"{brief_text}\n\n"
        f"THE EMBER (what this whole lineage ultimately serves):\n  {ember}\n\n"
        f"{torch['rite']}\n"
    )
    reply = ask_model(prompt, num_predict=400, torch=torch["id"], pid=pid)
    if reply is None:
        return None  # unusable output is a decline, not a guess
    line = next((l.strip() for l in reply.splitlines() if l.strip()), "")
    if not line or line.upper().startswith("DECLINE"):
        return None
    invocation = line.strip('"').strip()
    if not invocation or "<|" in invocation or len(invocation) < 10:
        return None
    return invocation


def choose_graph(brief_text: str, torch: dict, invocation: str, offerable=None, pid: str | None = None) -> str:
    """Which arrangement fits the invocation propose_kindling already wrote.

    A plain decision: the menu IS the torch's own options, which are the
    library's graph ids, so it cannot drift out of step with the library.
    Classifying a sentence that already exists against a fixed menu is a
    grounded task -- unlike inventing the sentence and picking the label
    in the same breath, which is what this replaced.
    """
    options = list(torch["options"])
    # docs/02 invariant 4: capability gating is applied at OFFER time. A
    # lineage that chose json storage cannot walk g.schema, whose root torch
    # requires sqlite -- so offering it produces a daughter that is dead on
    # arrival. `offerable` is the subset whose root torch this prophecy's
    # inherited capabilities actually permit.
    if offerable:
        keep = [o for o in options if o in offerable]
        if keep:
            options = keep
    prompt = (
        f"{brief_text}\n\n"
        f"The next generation will build this:\n\n  {invocation}\n\n"
        f"{torch['rite']}\n\n"
        "Reply with ONLY one of these exact option names, nothing else:\n"
        + ", ".join(options) + "\n\nOption:"
    )
    reply = ask_model(prompt, num_predict=200, torch=torch["id"], pid=pid)
    if reply is None:
        print(f"      (no usable reply -- defaulting to {options[0]!r})")
        return options[0]
    # longest first, so g.fullstack is not matched as a substring of g.full
    for opt in sorted(options, key=len, reverse=True):
        if opt in reply:
            return opt
    print(f"      (model said {reply!r}, matched no option -- defaulting to {options[0]!r})")
    return options[0]


def propose_mutations(brief_text: str, graph_edges: list, torch_ids: list, n: int = 3) -> list:
    """Ask the model for N graph mutations, in the only vocabulary the
    engine will accept. Anything that isn't one of these three shapes is
    dropped rather than coerced -- the engine does not take prose."""
    wiring = "\n".join(f"  {e['src']} -[{e['label']}]-> {e['dst'] or '(end)'}" for e in graph_edges)
    labels = sorted({f"{e['src']} / {e['label']}" for e in graph_edges})
    prompt = (
        f"{brief_text}\n\n"
        f"The graph currently walks:\n{wiring}\n\n"
        f"Torches available in the library to splice in:\n  {', '.join(torch_ids)}\n\n"
        "The ONLY (torch, label) pairs that exist are:\n  "
        + "\n  ".join(labels) + "\n"
        "Every src/after and label you use MUST be copied exactly from that list. "
        "Inventing a label makes the proposal unusable.\n\n"
        f"Propose {n} DIFFERENT improvements to this graph, as JSON, one per line, no other text.\n"
        "Each must be exactly one of:\n"
        '  {"op":"insert","torch":"<library torch>","after":"<torch>","label":"<edge label>"}\n'
        '  {"op":"rewire","src":"<torch>","label":"<edge label>","dst":"<torch>"}\n'
        '  {"op":"drop","torch":"<torch>"}\n\n'
        "JSON lines:"
    )
    reply = ask_model(prompt, num_predict=900)
    if reply is None:
        return []
    out = []
    for line in reply.splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if m.get("op") in ("insert", "rewire", "drop"):
            out.append(m)
    return out[:n]


def strip_fence(text: str) -> str:
    """Pull code out of a markdown fence if the model wrapped it in one."""
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            body = parts[1]
            if "\n" in body:
                first, rest = body.split("\n", 1)
                if first.strip().lower() in ("python", "python3", "py", ""):
                    return rest
            return body
    return text


def author_feature(brief_text: str, torch: dict, invocation: str, existing: str) -> str | None:
    """Ask the model to write the actual feature. Returns file contents."""
    prompt = (
        f"{brief_text}\n\n"
        f"{torch['rite']}\n\n"
        f"What this prophecy must implement:\n  {invocation}\n\n"
        + (f"The file currently contains:\n{existing}\n\n" if existing else "")
        + "Reply with the complete contents of cli.py and nothing else. No explanation.\n"
    )
    reply = ask_model(prompt, num_predict=1800)
    if reply is None:
        return None
    code = strip_fence(reply).strip()
    if "def " not in code and "import " not in code and "print" not in code:
        return None
    return code + "\n"


def receipt(pid: str) -> None:
    """Evidence read back off disk after a generation.

    Status lines lie: three generations once reported `pass` while writing
    byte-identical stub files, and a test suite reported `pass` with no
    tests in it. A receipt is regenerated from the artifact, so a claim
    that didn't happen can't be printed.
    """
    try:
        st = http_json(f"{BRIDGE}/api/state?pid={pid}")
        dest = st["dest"]
    except Exception as e:
        print(f"    receipt unavailable: {e}")
        return
    print("    -- receipt (read from disk) --")
    files = http_json(f"{BRIDGE}/api/file?pid={pid}")["files"]
    for name in sorted(files):
        print(f"       {len(files[name]):6d}B  {name}")
    for label, cmd in (("app", ["python3", "cli.py", "--help"]),
                       ("tests", ["sh", "run_tests.sh"])):
        try:
            r = subprocess.run(cmd, cwd=dest, capture_output=True, text=True, timeout=120)
            first = (r.stdout or r.stderr or "").strip().splitlines()
            summary = first[-1] if label == "tests" and first else (first[0] if first else "(no output)")
            print(f"       {label}: {'ok' if r.returncode == 0 else 'FAILED'} — {summary}")
        except Exception as e:
            print(f"       {label}: could not run ({e})")


def run_prophecy(pid: str, by_id: dict, ember: str, approve_kindle=None, on_event=None, should_stop=None) -> tuple[str | None, str | None, str]:
    """Walk one prophecy to completion.

    Returns (next_graph, next_invocation, reason). next_invocation is None
    when no daughter should be spawned; next_graph is which arrangement the
    daughter walks, chosen at the kindling torch rather than fixed for the
    whole lineage. reason explains why the walk ended.

    approve_kindle(invocation, offerable) -> (accepted, graph), when given,
    is consulted the moment kindle.next proposes a sentence, before this
    writes `written` and before choose.graph is ever reached -- the CLI's
    own unattended runs never pass this (None preserves exactly the old
    behavior: always proceed, let choose_graph classify it), but the
    server-side runner's "approve each generation" mode uses it to block
    here until a person decides, instead of kindling blind. on_event(dict),
    when given, is called after every successful light -- the runner's only
    hook into this walk for the UI's live event stream; this function stays
    unaware of HTTP, SSE or any of that. should_stop(), when given, is
    checked before every single torch -- a Halt click has to land within
    one step, not wait out the rest of a 45-step generation (each step is
    a real model call with a real model, so that wait is real minutes, not
    an abstraction).
    """
    next_invocation = None
    next_graph = None
    approved_graph = None
    seen = {}
    for step in range(1, MAX_STEPS_PER_PROPHECY + 1):
        if should_stop is not None and should_stop():
            return next_graph, next_invocation, f"stopped after {step - 1} step(s)"
        state = http_json(f"{BRIDGE}/api/state?pid={pid}")
        frontier = [t for t in state["frontier"] if t]
        if not frontier:
            return next_graph, next_invocation, f"walk complete after {step - 1} step(s)"

        torch_id = frontier[0]
        torch = by_id[torch_id]
        brief = http_json(f"{BRIDGE}/api/brieftext?pid={pid}&torch={torch_id}")["text"]

        seen[torch_id] = seen.get(torch_id, 0) + 1
        if seen[torch_id] > 3 and torch_id != "repair.test":
            return next_graph, next_invocation, f"stuck: {torch_id} repeated {seen[torch_id]} times"
        # a wrong test must not be able to loop forever against right code
        if torch_id == "repair.test" and seen[torch_id] > 2:
            q = http_json(f"{BRIDGE}/api/quarantine", {"pid": pid})
            print(f"  [{step}] quarantined unfixable test(s): {q['quarantined']}")
            if not q["quarantined"]:
                print("         nothing actually failing -- stopping this prophecy")
                return next_graph, next_invocation, "test suite disagreed with itself"
            # the suite is re-lit from the frontier and should now pass on
            # its own; it cannot be forced, and should not be.
            continue

        print(f"  [{step}] {torch_id} ({torch['kind']})")

        if torch["kind"] == "authoring":
            r = http_json(f"{BRIDGE}/api/authorize", {"pid": pid, "torch": torch_id})
            if "error" in r:
                print(f"      {r['error']}")
            else:
                print(f"      wrote {r['path']} ({r['bytes']} bytes)")
            option = torch["options"][0]
        elif torch["kind"] == "kindling":
            if EVOLVE:
                muts = propose_mutations(brief, GRAPH_EDGES, list(by_id), n=3)
                if muts:
                    print(f"      racing {len(muts)} proposed graph variants in sandboxes...")
                    res = http_json(f"{BRIDGE}/api/evolve", {"pid": pid, "mutations": muts}, timeout=900)
                    if "error" in res:
                        print(f"      evolution failed: {res['error']}")
                    else:
                        for row in res["scores"]:
                            mark = "  <- kept" if row["variant"] == res["winner"] else ""
                            print(f"        variant {row['variant']} ({row['op']}): {row['score']}  {row['detail']}{mark}")
                else:
                    print("      no usable mutations proposed")
            next_invocation = propose_kindling(brief, torch, ember, pid=pid)
            if next_invocation and approve_kindle is not None:
                accepted, chosen = approve_kindle(next_invocation, state.get("offerable") or [])
                if accepted:
                    approved_graph = chosen
                    option = "written"
                else:
                    next_invocation = None
                    option = "decline"
            else:
                option = "written" if next_invocation else "decline"
            if next_invocation:
                print(f"      proposes building: {next_invocation}")
            else:
                print("      declines to kindle")
        elif torch_id == "choose.graph":
            # reached only after kindle.next wrote `written`, so
            # next_invocation is always set here -- the decline edge goes
            # straight to the terminal and never reaches this torch.
            # approved_graph, when set, is a person's decision from
            # approve_kindle above and is used as-is, with no model call
            # asking it to reclassify a sentence a human already matched.
            next_graph = approved_graph or choose_graph(brief, torch, next_invocation, state.get("offerable"), pid=pid)
            option = next_graph
            print(f"      fits: {next_graph}")
        else:
            option = choose_option(brief, torch, pid=pid)
            if torch["kind"] != "validation":
                print(f"      chose {option!r}")

        result = http_json(f"{BRIDGE}/api/light", {"pid": pid, "torch": torch_id, "option": option})
        res = result["result"]
        if "error" in res:
            return next_graph, next_invocation, f"error: {res['error']}"
        if torch["kind"] == "validation":
            print(f"      check ran, outcome: {res['option']!r}")
        if res["filesWritten"]:
            print(f"      {res['filesWritten']} file(s) written")
        if on_event:
            on_event({
                "torch": torch_id, "kind": torch["kind"], "option": res["option"],
                "filesWritten": res["filesWritten"],
            })

    return next_graph, next_invocation, f"hit the {MAX_STEPS_PER_PROPHECY}-step ceiling"


def main():
    global EVOLVE, GRAPH_EDGES, BRIDGE
    ap = argparse.ArgumentParser()
    ap.add_argument("ember", nargs="*", default=["a small python cli tool"])
    ap.add_argument("--graph", default="g.found",
                    help="the arrangement the FOUNDING prophecy walks; every later\n"
                         " generation picks its own at its kindling torch")
    ap.add_argument("--generations", type=int, default=0,
                    help="stop after this many prophecies; 0 means run until the\n"
                         " hearth's own ceilings stop it, which is the point")
    ap.add_argument("--evolve", action="store_true",
                    help="breed competing graph variants at each kindling site")
    ap.add_argument("--bridge", default="http://127.0.0.1:8420", help="bridge base URL")
    ap.add_argument("--fresh-dirs", action="store_true",
                    help="give each daughter its own empty directory instead of extending the parent's")
    args = ap.parse_args()
    ember = " ".join(args.ember)
    EVOLVE = args.evolve
    BRIDGE = args.bridge

    print(f"ember: {ember}\n")
    begun = http_json(f"{BRIDGE}/api/begin", {
        "invocation": ember, "graph": args.graph, "evolution": args.evolve,
    })
    hid, pid = begun["hearth"], begun["pid"]
    print(f"hearth {hid} lit\n")

    graph = http_json(f"{BRIDGE}/api/graph")
    by_id = {n["id"]: n for n in graph["nodes"]}
    ALL_EDGES = graph["edges"]
    GRAPH_EDGES = [e for e in ALL_EDGES if e["graph"] == args.graph]

    generation = 1
    while True:
        state = http_json(f"{BRIDGE}/api/state?pid={pid}")
        print(f"--- generation {generation}: {pid} ---")
        print(f"    invocation: {state['invocation']}")

        next_graph, next_invocation, reason = run_prophecy(pid, by_id, ember)
        print(f"    prophecy ended ({reason})")
        http_json(f"{BRIDGE}/api/endreason", {"pid": pid, "reason": reason})
        receipt(pid)

        if not next_invocation:
            print("\nlineage ends: nothing further proposed.")
            break
        if args.generations and generation >= args.generations:
            print(f"\nlineage stopped: hit the --generations ceiling ({args.generations}).")
            break

        try:
            spawned = http_json(f"{BRIDGE}/api/kindle", {
                "pid": pid, "invocation": next_invocation,
                "graph": next_graph, "brownfield": not args.fresh_dirs,
            })
        except urllib.error.HTTPError as e:
            print(f"\nlineage stopped: kindle failed ({e})")
            break
        if "error" in spawned:
            print(f"\nlineage stopped: {spawned['error']}")
            break

        pid = spawned["pid"]
        # evolution proposes mutations to whichever graph is being walked,
        # so the edge list has to follow the daughter's choice
        GRAPH_EDGES = [e for e in ALL_EDGES if e["graph"] == next_graph]
        generation += 1
        print()

    print("\n=== lineage ===")
    for row in http_json(f"{BRIDGE}/api/lineage?hearth={hid}"):
        parent = row["parent"] or "-"
        print(f"  gen {row['generation']}  {row['id']}  (parent {parent})  {row['invocation']}")
        final = http_json(f"{BRIDGE}/api/state?pid={row['id']}")
        for f in final["tree"]:
            print(f"      {f}")


if __name__ == "__main__":
    main()
