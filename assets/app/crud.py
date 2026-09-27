"""Shared CRUD mechanics, written once so no generated module repeats them.

Every per-operation module in api/ is a handful of lines that names a table
and calls in here. That split is deliberate: when a generated route is
wrong, the bug is either in ONE tiny module (visible immediately) or in
this file (fixed once, for every resource in the app at the same time).
"""
from app import db, errors


def all_rows(table):
    return db.query("select * from %s order by id" % table)


def one_row(table, rid):
    rows = db.query("select * from %s where id=?" % table, (rid,))
    if not rows:
        raise errors.NotFound("no %s with id %s" % (table, rid))
    return rows[0]


def row_id(req):
    """The :id path segment, as an int, or a typed 404."""
    try:
        return int(req.params["id"])
    except (KeyError, ValueError, TypeError):
        raise errors.NotFound("id must be a number")


def insert(table, fields, data):
    missing = [f for f in fields if f not in data]
    if missing:
        raise errors.Invalid("missing field(s): " + ", ".join(missing))
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    rid = db.execute(
        "insert into %s(%s) values (%s)" % (table, cols, marks),
        tuple(data[f] for f in fields))
    return one_row(table, rid)


def update(table, fields, rid, data):
    present = [f for f in fields if f in data]
    if not present:
        raise errors.Invalid("nothing to update")
    one_row(table, rid)
    sets = ", ".join(f + "=?" for f in present)
    db.execute("update %s set %s where id=?" % (table, sets),
               tuple(data[f] for f in present) + (rid,))
    return one_row(table, rid)


def delete(table, rid):
    one_row(table, rid)
    db.execute("delete from %s where id=?" % table, (rid,))
