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
import urllib.error
import urllib.request

BRIDGE = "http://127.0.0.1:8420"
OLLAMA = "http://localhost:11434"
MODEL = "torch-gpt-oss"
MAX_STEPS_PER_PROPHECY = 30
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


def ask_model(prompt: str, num_predict: int = 600) -> str | None:
    """Call the local model. None means it produced nothing usable."""
    for budget in (num_predict, num_predict * 3):
        res = http_json(f"{OLLAMA}/api/generate", {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": budget},
        })
        text = _extract(res.get("response", ""))
        if text is not None:
            return text
        # ran out of budget mid-reasoning; give it more room once
    return None


def choose_option(brief_text: str, torch: dict) -> str:
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
    reply = ask_model(prompt)
    if reply is None:
        print(f"      (no usable reply -- defaulting to {options[0]!r})")
        return options[0]
    lowered = reply.lower()
    for opt in options:
        if opt.lower() in lowered:
            return opt
    print(f"      (model said {reply!r}, matched no option -- defaulting to {options[0]!r})")
    return options[0]


def propose_next_invocation(brief_text: str, torch: dict, ember: str) -> str | None:
    """Ask the model for the daughter's invocation. None means decline."""
    prompt = (
        f"{brief_text}\n\n"
        f"THE EMBER (what this whole lineage ultimately serves):\n  {ember}\n\n"
        f"{torch['rite']}\n\n"
        "Reply with ONE sentence describing the single next thing to build, and nothing else.\n"
        "If nothing worthwhile remains, or the next step would not serve the ember, reply with exactly: DECLINE\n\n"
        "Next:"
    )
    reply = ask_model(prompt, num_predict=800)
    if reply is None:
        return None  # unusable output is treated as a decline, not a guess
    first_line = next((l.strip() for l in reply.splitlines() if l.strip()), "")
    if not first_line or first_line.upper().startswith("DECLINE"):
        return None
    candidate = first_line.strip('"').strip()
    # never let harmony markup or a truncated fragment become an invocation
    if "<|" in candidate or len(candidate) < 10:
        return None
    return candidate


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


def run_prophecy(pid: str, by_id: dict, ember: str) -> tuple[str | None, str]:
    """Walk one prophecy to completion.

    Returns (next_invocation, reason). next_invocation is None when no
    daughter should be spawned; reason explains why the walk ended.
    """
    next_invocation = None
    seen = {}
    for step in range(1, MAX_STEPS_PER_PROPHECY + 1):
        state = http_json(f"{BRIDGE}/api/state?pid={pid}")
        frontier = [t for t in state["frontier"] if t]
        if not frontier:
            return next_invocation, f"walk complete after {step - 1} step(s)"

        torch_id = frontier[0]
        torch = by_id[torch_id]
        brief = http_json(f"{BRIDGE}/api/brieftext?pid={pid}&torch={torch_id}")["text"]

        seen[torch_id] = seen.get(torch_id, 0) + 1
        if seen[torch_id] > 3 and torch_id != "repair.test":
            return next_invocation, f"stuck: {torch_id} repeated {seen[torch_id]} times"
        # a wrong test must not be able to loop forever against right code
        if torch_id == "repair.test" and seen[torch_id] > 2:
            q = http_json(f"{BRIDGE}/api/quarantine", {"pid": pid})
            print(f"  [{step}] quarantined unfixable test(s): {q['quarantined']}")
            if not q["quarantined"]:
                print("         nothing actually failing -- stopping this prophecy")
                return next_invocation, "test suite disagreed with itself"
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
            next_invocation = propose_next_invocation(brief, torch, ember)
            option = "spawn" if next_invocation else "decline"
            if next_invocation:
                print(f"      proposes: {next_invocation}")
            else:
                print("      declines to kindle")
        else:
            option = choose_option(brief, torch)
            if torch["kind"] != "validation":
                print(f"      chose {option!r}")

        result = http_json(f"{BRIDGE}/api/light", {"pid": pid, "torch": torch_id, "option": option})
        res = result["result"]
        if "error" in res:
            return next_invocation, f"error: {res['error']}"
        if torch["kind"] == "validation":
            print(f"      check ran, outcome: {res['option']!r}")
        if res["filesWritten"]:
            print(f"      {res['filesWritten']} file(s) written")

    return next_invocation, f"hit the {MAX_STEPS_PER_PROPHECY}-step ceiling"


def main():
    global EVOLVE, GRAPH_EDGES, BRIDGE
    ap = argparse.ArgumentParser()
    ap.add_argument("ember", nargs="*", default=["a small python cli tool"])
    ap.add_argument("--graph", default="g.pycli")
    ap.add_argument("--generations", type=int, default=3, help="stop after this many prophecies")
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
    GRAPH_EDGES = [e for e in graph["edges"] if e["graph"] == args.graph]

    generation = 1
    while True:
        state = http_json(f"{BRIDGE}/api/state?pid={pid}")
        print(f"--- generation {generation}: {pid} ---")
        print(f"    invocation: {state['invocation']}")

        next_invocation, reason = run_prophecy(pid, by_id, ember)
        print(f"    prophecy ended ({reason})")
        receipt(pid)

        if not next_invocation:
            print("\nlineage ends: nothing further proposed.")
            break
        if generation >= args.generations:
            print(f"\nlineage stopped: hit the --generations ceiling ({args.generations}).")
            break

        try:
            spawned = http_json(f"{BRIDGE}/api/kindle", {
                "pid": pid, "invocation": next_invocation,
                "graph": args.graph, "brownfield": not args.fresh_dirs,
            })
        except urllib.error.HTTPError as e:
            print(f"\nlineage stopped: kindle failed ({e})")
            break
        if "error" in spawned:
            print(f"\nlineage stopped: {spawned['error']}")
            break

        pid = spawned["pid"]
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
