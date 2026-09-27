#!/usr/bin/env python3
"""The gate on a declared resource spec.

Parses .resource-spec.txt with the shared grammar and rejects anything
that doesn't fit it, or names a table that already exists. This is law
checking that a choice was expressed correctly -- exactly the same job
a decision torch's option-matching does, just against a slightly richer
grammar than a fixed enumerated menu.

    python3 tools/checkresource.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SPEC_FILE = ROOT / ".resource-spec.txt"


def main():
    if not SPEC_FILE.exists():
        print("FAIL no .resource-spec.txt was written")
        return 1

    from parseresource import parse, SpecError
    try:
        table, fields = parse(SPEC_FILE.read_text())
    except SpecError as e:
        print("FAIL %s" % e)
        return 1

    try:
        import survey
        existing = {t["table"] for t in survey.tables()}
    except Exception:
        existing = set()
    if table in existing:
        print("FAIL table %r already exists -- pick a new resource, "
              "or the migration graph to add a column to it" % table)
        return 1

    print("ok   table=%s fields=%s" % (
        table, ", ".join("%s:%s" % f for f in fields)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
