#!/usr/bin/env python3
"""Make runs/ legible.

Hearth and prophecy directories are named with random hex, which is fine
for uniqueness and useless for a human browsing a file tree: there is no
date, no sign of what was being built, and no way to tell a finished run
from one that was killed after two minutes.

Everything needed is already recorded -- the hearths table has `born` and
the ember, prophecies have generation and invocation. The complication is
that each schema change moved db aside, so the history is spread across
db/ and every db.* backup. This reads all of them, joins against what is
actually on disk, and writes runs/INDEX.md.

    python3 runs.py            # print the index
    python3 runs.py --write    # also write runs/INDEX.md
"""

import datetime as dt
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(REPO, "runs")


def q_json(dbdir, expr):
    """Run one expression against a specific db directory."""
    # hsym `$"..." rather than a bare `:path symbol: the backup dirs are
    # named db.pre-plugin and friends, and q parses the dot as a namespace
    # separator, so the literal form fails on every one of them.
    script = (
        f'HH: get hsym `$"{dbdir}/hearths";\n'
        f'PP: get hsym `$"{dbdir}/prophecies";\n'
        f"res: {expr};\n-1 .j.j res;\nexit 0\n"
    )
    try:
        p = subprocess.run(["q", "-q"], input=script, capture_output=True,
                           text=True, cwd=REPO, timeout=30)
        line = (p.stdout or "").strip().splitlines()
        return json.loads(line[-1]) if line else []
    except Exception:
        return []


def gather():
    """Every hearth we have any record of, from every db snapshot."""
    seen = {}
    dbs = [d for d in os.listdir(REPO)
           if d == "db" or d.startswith("db.")]
    for d in sorted(dbs):
        full = os.path.join(REPO, d)
        if not os.path.exists(os.path.join(full, "hearths")):
            continue
        for h in q_json(d, "0!select id,born,ember from HH"):
            hid = h.get("id")
            if hid and hid not in seen:
                seen[hid] = {"born": h.get("born"), "ember": h.get("ember"), "src": d}
        for p in q_json(d, "0!select id,hearth,generation,invocation,dest from PP"):
            hid = p.get("hearth")
            if hid in seen:
                seen[hid].setdefault("gens", []).append(p)
                # the hearth's directory is the parent of any prophecy dest,
                # whatever it happens to be called
                dest = p.get("dest") or ""
                if dest:
                    seen[hid].setdefault("dir", os.path.basename(os.path.dirname(dest)))
    return seen


def app_summary(path):
    """What the thing in this directory actually is, asked of the thing."""
    cli = os.path.join(path, "cli.py")
    if not os.path.isfile(cli):
        return "-", "no cli.py"
    try:
        r = subprocess.run(["python3", "cli.py", "--help"], cwd=path,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return "broken", (r.stderr or "").strip().splitlines()[-1][:60] if r.stderr else "nonzero exit"
        for line in (r.stdout or "").splitlines():
            if line.startswith("usage:") and "{" in line:
                return "runs", line[line.index("{"):].strip()
        return "runs", "no subcommands"
    except Exception as e:
        return "broken", str(e)[:60]


def main():
    meta = gather()
    by_dir = {v["dir"]: (k, v) for k, v in meta.items() if v.get("dir")}
    by_dir.update({k: (k, v) for k, v in meta.items()})  # old bare-hash dirs
    rows = []
    for name in sorted(os.listdir(RUNS)):
        path = os.path.join(RUNS, name)
        if not os.path.isdir(path) or name.startswith("_"):
            continue
        hid, info = by_dir.get(name, (name, {}))
        born = info.get("born")
        if born:
            when = born.replace("D", " ")[:16]
        else:
            when = dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y.%m.%d %H:%M")
        gens = info.get("gens", [])
        # the working directory is the first prophecy's; later generations
        # share it, so the app lives one level down
        subs = [d for d in sorted(os.listdir(path)) if os.path.isdir(os.path.join(path, d))]
        appdir = os.path.join(path, subs[0]) if subs else path
        state, detail = app_summary(appdir)
        nfeat = len([f for f in os.listdir(os.path.join(appdir, "features"))
                     if f.startswith("gen")]) if os.path.isdir(os.path.join(appdir, "features")) else 0
        ntest = len([f for f in os.listdir(os.path.join(appdir, "tests"))
                     if f.endswith(".sh")]) if os.path.isdir(os.path.join(appdir, "tests")) else 0
        rows.append({
            "dir": name[:38], "when": when,
            "ember": (info.get("ember") or "(no record)")[:52],
            "gens": len(gens) or len(subs),
            "feats": nfeat, "tests": ntest,
            "state": state, "detail": detail,
        })

    rows.sort(key=lambda r: r["when"])
    hdr = f"{'when':17} {'dir':38} {'gen':>3} {'ft':>3} {'ts':>3} {'state':8} ember"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['when']:17} {r['dir']:38} {r['gens']:>3} {r['feats']:>3} "
              f"{r['tests']:>3} {r['state']:8} {r['ember']}")

    if "--write" in sys.argv:
        out = [
            "# runs index",
            "",
            f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by `python3 runs.py --write`.",
            "",
            "`gen` generations, `ft` feature modules, `ts` tests. `state` is what",
            "`python3 cli.py --help` does in that directory right now.",
            "",
            "| when | dir | gen | ft | ts | state | ember | subcommands |",
            "|---|---|--:|--:|--:|---|---|---|",
        ]
        for r in rows:
            out.append(f"| {r['when']} | `{r['dir']}` | {r['gens']} | {r['feats']} | "
                       f"{r['tests']} | {r['state']} | {r['ember']} | `{r['detail']}` |")
        with open(os.path.join(RUNS, "INDEX.md"), "w") as f:
            f.write("\n".join(out) + "\n")
        print(f"\nwrote {os.path.join(RUNS, 'INDEX.md')}")


if __name__ == "__main__":
    main()
