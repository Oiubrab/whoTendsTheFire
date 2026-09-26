#!/usr/bin/env python3
"""Drive a prophecy end to end using the local model, no human clicking.

At every frontier torch, asks torch-gpt-oss (our own downloaded gpt-oss-20b
GGUF, imported into Ollama) to pick one of that torch's options, using
exactly the context brieftext() builds -- invocation, rite, trail,
capabilities, live tree. Lights whatever it picks via the same /api/light
the UI uses, and keeps going until the frontier collapses to the terminal
symbol or a step budget runs out.
"""

import json
import sys
import time
import urllib.request

BRIDGE = "http://127.0.0.1:8420"
OLLAMA = "http://localhost:11434"
MODEL = "torch-gpt-oss"
MAX_STEPS = 30


def http_json(url, data=None, timeout=120):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def ask_model(prompt: str) -> str:
    """Call the local model, strip Harmony channel markup, return the final message."""
    res = http_json(f"{OLLAMA}/api/generate", {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 300},
    })
    raw = res.get("response", "")
    if "<|channel|>final<|message|>" in raw:
        raw = raw.rsplit("<|channel|>final<|message|>", 1)[1]
    for stop in ("<|end|>", "<|return|>", "<|start|>"):
        raw = raw.split(stop)[0]
    return raw.strip()


def choose_option(brief_text: str, torch: dict) -> str:
    options = torch["options"]
    if len(options) == 1:
        return options[0]  # nothing to decide
    if torch["kind"] == "validation":
        # pass/fail is decided by codeOk once the check actually runs, not
        # guessed beforehand -- light[] ignores whatever we send here anyway.
        return options[0]
    prompt = (
        f"{brief_text}\n\n"
        f"You are standing at torch '{torch['id']}' ({torch['kind']}).\n"
        + (f"Its question: {torch['rite']}\n" if torch["rite"] else "")
        + f"Choose exactly one of these options and reply with ONLY that option's exact text, nothing else:\n"
        + ", ".join(options)
        + "\n\nOption:"
    )
    reply = ask_model(prompt)
    lowered = reply.lower()
    for opt in options:
        if opt.lower() in lowered:
            return opt
    print(f"    (model said {reply!r}, didn't match any option -- defaulting to {options[0]!r})")
    return options[0]


def main():
    invocation = " ".join(sys.argv[1:]) or "build me a small python cli tool"
    print(f"invocation: {invocation}")

    begun = http_json(f"{BRIDGE}/api/begin", {"invocation": invocation})
    pid = begun["pid"]
    dest = begun["state"]["dest"]
    print(f"prophecy: {pid}")
    print(f"dest:     {dest}\n")

    graph = http_json(f"{BRIDGE}/api/graph")
    by_id = {n["id"]: n for n in graph["nodes"]}

    for step in range(1, MAX_STEPS + 1):
        state = http_json(f"{BRIDGE}/api/state?pid={pid}")
        frontier = [t for t in state["frontier"] if t]
        if not frontier:
            print(f"\nprophecy ended after {step - 1} step(s).")
            break

        torch_id = frontier[0]
        torch = by_id[torch_id]
        brief = http_json(f"{BRIDGE}/api/brieftext?pid={pid}&torch={torch_id}")["text"]

        print(f"[{step}] at {torch_id} ({torch['kind']}) -- options: {torch['options']}")
        option = choose_option(brief, torch)
        if torch["kind"] != "validation":
            print(f"    -> chose {option!r}")

        result = http_json(f"{BRIDGE}/api/light", {"pid": pid, "torch": torch_id, "option": option})
        if "error" in result["result"]:
            print(f"    ERROR: {result['result']['error']}")
        elif torch["kind"] == "validation":
            print(f"    -> code ran, outcome: {result['result']['option']!r}")
        print(f"    files written: {result['result']['filesWritten']}, "
              f"code ok: {result['result']['codeOk']}, "
              f"next: {result['result']['next']}")
    else:
        print(f"\nstopped after hitting the {MAX_STEPS}-step budget.")

    final = http_json(f"{BRIDGE}/api/state?pid={pid}")
    print("\ncapabilities gained:", final["capabilities"])
    print("torches lit:", [t["torch"] for t in final["trail"]])
    print(f"\nfiles left in {dest}:")
    for f in final["tree"]:
        print(" ", f)


if __name__ == "__main__":
    main()
