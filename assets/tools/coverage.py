#!/usr/bin/env python3
"""Does every subcommand and route have a test that mentions it?

The failure this exists for: a generation adds `POST /api/thing2`, writes
a test that checks `/api/health` returns ok, and the suite passes. Both
tests in the app that prompted this checked only the scaffold's own health
endpoint. Neither touched the route its generation had just added, so the
suite was green on code that did not work.

This is a coverage floor, not a correctness check, and it is worth being
precise about the difference: it asks whether a test so much as NAMES the
thing, which is weak. It is still enough to stop a generation from
claiming a feature it never exercised, and it is entirely deterministic.
The round-trip check is what asks whether the thing actually works.

Quarantined tests do not count -- a test moved to quarantine is one the
system already admitted it could not make pass.

    python3 tools/coverage.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# provided by the scaffold, not by any generation, so nothing has to cover it
SCAFFOLD_ROUTES = {"/api/health", "/api/views"}


def test_text():
    d = ROOT / "tests"
    if not d.is_dir():
        return "", 0
    parts, n = [], 0
    for p in sorted(d.glob("*.sh")):
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
        n += 1
    return "\n".join(parts), n


def main():
    import survey
    text, ntests = test_text()

    subs = sorted({x["name"] for x in survey.subcommands() if x["name"]})
    routes = sorted({r["path"] for r in survey.routes()} - SCAFFOLD_ROUTES)

    if not subs and not routes:
        print("nothing registered yet -- nothing to cover")
        return 0
    if ntests == 0:
        print("FAIL %d subcommand(s) and %d route(s) exist and there are no tests"
              % (len(subs), len(routes)))
        return 1

    uncovered = []
    for name in subs:
        # a subcommand is covered if a test invokes it after cli.py
        if ("cli.py %s" % name) in text or ("cli.py  %s" % name) in text:
            print("ok   subcommand %-18s is exercised by a test" % name)
        else:
            uncovered.append("subcommand %s" % name)
    for path in routes:
        if path in text:
            print("ok   route      %-18s is exercised by a test" % path)
        else:
            uncovered.append("route %s" % path)

    for u in uncovered:
        print("FAIL %s has no test that even mentions it" % u)
    total = len(subs) + len(routes)
    print("%d of %d registered thing(s) covered, across %d test file(s)"
          % (total - len(uncovered), total, ntests))
    return 1 if uncovered else 0


if __name__ == "__main__":
    sys.exit(main())
