#!/usr/bin/env python3
"""Every torch must work: the torch test matrix.

selftest.sh walks one lineage down one set of branches, which leaves most
of the library untested -- the json store, a cli-only or http-only app,
six of the nine graphs, and every repair torch (they only light after a
failure, and a canned model never fails). This runs a matrix of canned
lineages chosen to cover every branch, with failures injected on purpose
(server.py's FAKE_BREAK / FAKE_BREAK_ALWAYS), and then demands:

  * every torch in the library was lit at least once, somewhere
  * no prophecy in any case ended on a failure -- each one either walked
    to completion or escalated to rollback.generation and carried on; the
    only way a lineage may end is kindle.next declining
  * every fail edge in every graph was actually taken (reported; a fail
    edge nothing can provoke yet is listed so it can be given a case)

    python3 torchtest.py           # the whole matrix
    python3 torchtest.py -k found  # only cases whose name contains "found"

Isolated: each case gets its own bridge, db and runs dir under /tmp.
Never touches db/ or runs/.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))

# name, founding choices, graphs each daughter walks in order, faults
CASES = [
    ("cli-json-feature", dict(FAKE_SURFACE="cli", FAKE_STORAGE="json", FAKE_LICENSE="unlicense",
                              FAKE_KINDLES="g.feature,g.harden,g.document", FAKE_BREAK="feature,test")),
    ("http-sqlite-route-view-schema", dict(FAKE_SURFACE="http", FAKE_STORAGE="sqlite", FAKE_LICENSE="apache",
                                           FAKE_KINDLES="g.route,g.view,g.schema",
                                           FAKE_BREAK="route,apitest,view,migration")),
    ("both-resource-fullstack", dict(FAKE_SURFACE="both", FAKE_STORAGE="sqlite", FAKE_LICENSE="mit",
                                     FAKE_KINDLES="g.resource,g.fullstack,g.harden", FAKE_BREAK="spec,test")),
    ("rollback-when-repair-never-converges", dict(FAKE_SURFACE="both", FAKE_STORAGE="sqlite", FAKE_LICENSE="mit",
                                                  FAKE_KINDLES="g.feature", FAKE_BREAK_ALWAYS="feature")),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read())


def run_case(name, env_extra):
    work = f"/tmp/wttf-torchtest/{name}"
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(f"{work}/db")
    os.makedirs(f"{work}/runs")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, FAKE_MODEL="1", DB_OVERRIDE=f"{work}/db", RUNS_OVERRIDE=f"{work}/runs", **env_extra)
    srv = subprocess.Popen([sys.executable, "server.py", str(port)], cwd=REPO, env=env,
                           stdout=open(f"{work}/bridge.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.2)
        agent = subprocess.run([sys.executable, "-u", "agent.py", f"torchtest {name}", "--bridge", base],
                               cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
        open(f"{work}/agent.log", "w").write(agent.stdout + agent.stderr)
        seen = []      # (graph, torch, option)
        ends = []      # (generation, graph, endreason)
        for h in get(base, "/api/hearths"):
            for row in get(base, f"/api/lineage?hearth={h['id']}"):
                st = get(base, f"/api/state?pid={row['id']}")
                ends.append((row["generation"], row["graph"], st["endreason"]))
                seen += [(row["graph"], t["torch"], t["option"]) for t in st["trail"]]
        lib = get(base, "/api/graph")
        return agent.returncode, seen, ends, lib, work
    finally:
        srv.terminate()
        srv.wait()


def main():
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else None
    cases = [c for c in CASES if not only or only in c[0]]
    all_seen, lib, failed = [], None, 0
    for name, env_extra in cases:
        rc, seen, ends, lib, work = run_case(name, env_extra)
        bad = [e for e in ends if not e[2].startswith("walk complete")]
        escalations = sum(1 for _, t, _ in seen if t == "escalate")
        ok = rc == 0 and not bad and len(ends) > 1
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {len(ends)} generation(s), {len(seen)} torches lit, "
              f"{escalations} escalation(s)")
        for g, graph, reason in bad:
            print(f"        generation {g} ({graph}) ended on: {reason}")
        if rc != 0:
            print(f"        agent exited {rc} -- see {work}/agent.log")
        if len(ends) <= 1:
            print(f"        lineage never kindled -- see {work}/agent.log")
        all_seen += seen

    if lib is None:
        return 1
    lit = {t for _, t, _ in all_seen}
    never = sorted(n["id"] for n in lib["nodes"] if n["id"] not in lit)
    taken = {(g, t, o) for g, t, o in all_seen}
    fail_edges = sorted({(e["graph"], e["src"]) for e in lib["edges"] if e["label"] == "fail"})
    untaken = [(g, t) for g, t in fail_edges if (g, t, "fail") not in taken]

    print()
    if never and not only:
        failed += 1
        print(f"FAIL  {len(never)} torch(es) never lit by any case: {', '.join(never)}")
    elif not only:
        print(f"PASS  every one of {len(lib['nodes'])} torches lit at least once")
    print(f"info  fail edges taken: {len(fail_edges) - len(untaken)} of {len(fail_edges)}")
    for g, t in untaken:
        print(f"        not provoked yet: {g} {t} -> fail")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
