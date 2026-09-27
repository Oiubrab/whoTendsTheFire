"""SQLite access and migrations. Standard library only.

Migrations are plain .sql files in migrations/, applied in filename
order, each recorded in a _migrations table so re-running is a no-op.
That ordering-by-name is deliberate law: it means a generation can add
a migration without knowing anything about the ones before it.
"""

import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "app.db"
MIGRATIONS = ROOT / "migrations"


def connect():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("pragma foreign_keys = on")
    return con


def _applied(con):
    con.execute("create table if not exists _migrations ("
                "name text primary key, applied_at text default current_timestamp)")
    return {r[0] for r in con.execute("select name from _migrations")}


def migrate(verbose=True):
    """Apply every unapplied migration. Returns the list applied."""
    con = connect()
    done = _applied(con)
    applied = []
    if MIGRATIONS.is_dir():
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                con.executescript(sql)
                con.execute("insert into _migrations(name) values (?)", (path.name,))
                con.commit()
            except sqlite3.Error as e:
                con.rollback()
                raise RuntimeError("migration %s failed: %s" % (path.name, e)) from e
            applied.append(path.name)
            if verbose:
                print("applied " + path.name)
    con.close()
    return applied


def query(sql, params=()):
    """Read rows as a list of plain dicts."""
    con = connect()
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def execute(sql, params=()):
    """Write. Returns lastrowid."""
    con = connect()
    try:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def tables():
    return [r["name"] for r in query(
        "select name from sqlite_master where type='table' "
        "and name not like 'sqlite_%' and name <> '_migrations' order by name")]
