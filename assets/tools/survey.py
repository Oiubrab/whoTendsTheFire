#!/usr/bin/env python3
"""Inventory of this codebase, derived rather than described.

Nothing here asks anyone what the project contains: it reads the tree
and the syntax trees. A model given this output is being handed facts,
not a summary it has to trust, and that is the whole point -- the
executive judgement ("what should come next") is worth a model call,
the inventory feeding it never is.

    python3 tools/survey.py            # human-readable
    python3 tools/survey.py --json     # machine-readable
"""

import ast
import json
import os
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "quarantine"}


def pyfiles(*rel):
    for r in rel:
        d = ROOT / r
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            yield p


def parse(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


def str_of(node):
    """The literal string a node denotes, or None if it isn't one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def subcommands():
    """Every name passed to sub.add_parser(...) across features/."""
    found = []
    for p in pyfiles("features"):
        tree = parse(p)
        if tree is None:
            found.append({"module": p.name, "name": None, "broken": True})
            continue
        names = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == "add_parser" and node.args:
                nm = str_of(node.args[0])
                if nm:
                    names.append(nm)
        for nm in names:
            found.append({"module": p.name, "name": nm, "broken": False})
        if not names and p.name not in ("__init__.py", "store.py"):
            found.append({"module": p.name, "name": None, "broken": False})
    return found


def routes():
    """Every path passed to routes.add(...) or a ROUTES dict across api/."""
    found = []
    for p in pyfiles("api"):
        tree = parse(p)
        if tree is None:
            found.append({"module": p.name, "path": None, "broken": True})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr == "add" and len(node.args) >= 2:
                    meth, pth = str_of(node.args[0]), str_of(node.args[1])
                    if pth:
                        found.append({"module": p.name, "method": meth or "?",
                                      "path": pth, "broken": False})
    return found


def functions():
    """Top-level functions per module, so callable surface is visible."""
    out = {}
    for p in pyfiles("app", "features", "api"):
        tree = parse(p)
        if tree is None:
            continue
        rel = str(p.relative_to(ROOT))
        out[rel] = [n.name for n in tree.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not n.name.startswith("_")]
    return out


def tables():
    """Tables in the sqlite database, if one has been built."""
    db = ROOT / "app.db"
    if not db.exists():
        return []
    try:
        con = sqlite3.connect(str(db))
        rows = con.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' and name <> '_migrations' "
            "order by name").fetchall()
        out = []
        for (name,) in rows:
            cols = [c[1] for c in con.execute("pragma table_info(%s)" % name)]
            n = con.execute("select count(*) from %s" % name).fetchone()[0]
            out.append({"table": name, "columns": cols, "rows": n})
        con.close()
        return out
    except sqlite3.Error as e:
        return [{"table": "(error)", "columns": [], "rows": 0, "error": str(e)}]


def migrations():
    d = ROOT / "migrations"
    return sorted(p.name for p in d.glob("*.sql")) if d.is_dir() else []


def views():
    # .js only: the directory also holds a .keep placeholder, and listing it
    # as a view puts a file that renders nothing into every later brief
    d = ROOT / "web" / "views"
    return sorted(p.name for p in d.glob("*.js")) if d.is_dir() else []


def tests():
    d = ROOT / "tests"
    if not d.is_dir():
        return {"active": [], "quarantined": []}
    q = d / "quarantine"
    return {
        "active": sorted(p.name for p in d.glob("*.sh")),
        "quarantined": sorted(p.name for p in q.glob("*.sh")) if q.is_dir() else [],
    }


def collect():
    return {
        "subcommands": subcommands(),
        "routes": routes(),
        "functions": functions(),
        "tables": tables(),
        "migrations": migrations(),
        "views": views(),
        "tests": tests(),
    }


def render(s):
    L = []
    subs = [x for x in s["subcommands"] if x["name"]]
    L.append("SUBCOMMANDS (%d)" % len(subs))
    for x in subs:
        L.append("  %-20s  %s" % (x["name"], x["module"]))
    dead = [x for x in s["subcommands"] if not x["name"]]
    for x in dead:
        L.append("  %-20s  %s%s" % ("(none registered)", x["module"],
                                    "  BROKEN SYNTAX" if x["broken"] else ""))

    L.append("")
    L.append("HTTP ROUTES (%d)" % len(s["routes"]))
    for x in s["routes"]:
        L.append("  %-6s %-24s  %s" % (x.get("method", "?"), x["path"], x["module"]))

    L.append("")
    L.append("DATABASE")
    if not s["tables"]:
        L.append("  (no app.db yet)")
    for t in s["tables"]:
        L.append("  %s(%s)  %d row(s)" % (t["table"], ", ".join(t["columns"]), t["rows"]))
    if s["migrations"]:
        L.append("  migrations: " + ", ".join(s["migrations"]))

    L.append("")
    L.append("MODULES")
    for mod, fns in sorted(s["functions"].items()):
        L.append("  %-28s %s" % (mod, ", ".join(fns) or "-"))

    if s["views"]:
        L.append("")
        L.append("WEB VIEWS")
        for v in s["views"]:
            L.append("  " + v)

    t = s["tests"]
    L.append("")
    L.append("TESTS  %d active, %d quarantined" % (len(t["active"]), len(t["quarantined"])))
    return "\n".join(L)


def main():
    s = collect()
    if "--json" in sys.argv:
        print(json.dumps(s, indent=2))
    else:
        print(render(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
