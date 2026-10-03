#!/usr/bin/env python3
"""Did this generation actually change anything, or did it just run in
place?

Every generation ends in a real git commit. That commit is the one
mechanical signal available for "did this generation do anything" --
not a model's own account of itself, which is exactly what produced the
failure this exists for: four real-model generations in a row each
wrote an invocation describing a feature to build, picked g.harden to
pursue it, and g.harden has no authoring torches at all. Nothing was
ever built. The test suite stayed empty, which made it report "no tests
found" as a failure, which the next kindling call read as "something is
broken, prefer g.harden" -- a closed loop that produced four generations
and zero progress.

This is the fix at the law level, not the rite level: if a generation's
own commit touched nothing but the files every generation refreshes
automatically regardless of what it built (SURVEY.txt, the generated
docs, the regenerated README block), it did not do anything, and the
graph this is wired into routes that straight to a dead end rather than
to kindle.next. A lineage that cannot make progress stops producing
generations instead of producing empty ones forever.

    python3 tools/progresscheck.py
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# touched by nearly every generation regardless of whether it built
# anything -- survey.run and docs.generate run unconditionally in every
# graph. A generation that changed ONLY these made no real progress.
HOUSEKEEPING = {"SURVEY.txt", "docs/USAGE.md", "README.md"}


def git(args):
    r = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def main():
    rc, out, err = git(["rev-parse", "--verify", "HEAD"])
    if rc != 0:
        print("FAIL no commit exists yet -- git.commit should have made one")
        return 1

    rc, out, err = git(["rev-parse", "--verify", "HEAD~1"])
    if rc != 0:
        # the very first commit in a fresh repo: nothing to diff against,
        # and a founding generation always writes dozens of real files,
        # so there is nothing meaningful this check could add here.
        print("ok   first commit in this repo -- nothing to compare against")
        return 0

    rc, out, err = git(["diff", "--name-only", "HEAD~1", "HEAD"])
    if rc != 0:
        print("FAIL git diff failed: %s" % err.strip())
        return 1

    changed = [line.strip() for line in out.splitlines() if line.strip()]
    real = [f for f in changed if f not in HOUSEKEEPING]

    if not changed:
        print("FAIL the last commit changed nothing at all")
        return 1
    if not real:
        print("FAIL the last commit touched only housekeeping file(s): %s"
              % ", ".join(sorted(changed)))
        print("     nothing was actually built or changed this generation")
        return 1

    print("ok   %d real file(s) changed: %s"
          % (len(real), ", ".join(sorted(real)[:8]) + (", ..." if len(real) > 8 else "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
