#!/usr/bin/env python3
"""Apply migrations, then read the schema back out of sqlite.

The check that matters is not "did the SQL look right" but "does the
database now actually contain a table with columns". Applying and then
re-reading is the only way to know, and it is entirely deterministic --
sqlite either accepted the DDL or it did not.

    python3 tools/schemacheck.py
"""

import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    mig = ROOT / "migrations"
    files = sorted(mig.glob("*.sql")) if mig.is_dir() else []
    if not files:
        print("FAIL no migrations in migrations/ -- nothing defines a schema")
        return 1

    try:
        from app import db
    except ImportError as e:
        print("FAIL cannot import app.db: %s" % e)
        return 1

    try:
        applied = db.migrate(verbose=False)
    except RuntimeError as e:
        print("FAIL %s" % e)
        return 1
    except sqlite3.Error as e:
        print("FAIL sqlite rejected a migration: %s" % e)
        return 1

    print("%d migration file(s), %d newly applied" % (len(files), len(applied)))

    names = db.tables()
    if not names:
        print("FAIL migrations applied but the database has no tables")
        return 1

    con = db.connect()
    problems = 0
    for t in names:
        cols = [r["name"] for r in con.execute("pragma table_info(%s)" % t)]
        if not cols:
            print("FAIL table %s has no columns" % t)
            problems += 1
            continue
        n = con.execute("select count(*) from %s" % t).fetchone()[0]
        print("ok   %s(%s)  %d row(s)" % (t, ", ".join(cols), n))

    # a foreign key pointing at a table that was never created is a real
    # defect that only shows up on read-back
    bad = con.execute("pragma foreign_key_check").fetchall()
    if bad:
        print("FAIL %d foreign key violation(s)" % len(bad))
        problems += 1
    con.close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
