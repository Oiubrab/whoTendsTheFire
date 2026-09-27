#!/usr/bin/env python3
"""Render one small file from one small template, given a resource spec.

Each `emit` below is exactly one torch's worth of work: one template, one
output file, one thing that can be wrong. That granularity is the point --
when a generated route misbehaves the blast radius is a ten-line module,
not a two-hundred-line one, and the repair is scoped to it.

The templates are real files under assets/templates/, not strings built up
inside this script. That is also deliberate: the first version of this tool
assembled shell and JSON by nesting quotes inside Python %-formatting and
shipped two escaping bugs in a row. A template you can run, lint and read
as an ordinary file cannot hide that class of mistake.

Spec grammar, one line, in .resource-spec.txt:

    name: field:type, field:type, ...

types: text | integer | real | boolean. id and created_at are automatic.
The grammar itself lives in parseresource.py, shared with checkresource.py
(the validation-torch gate) so the two can never disagree about what a
valid spec looks like -- this file only renders once a spec has already
passed that gate.

    python3 tools/resource.py check
    python3 tools/resource.py emit api-create
    python3 tools/resource.py selftest
"""

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
SPEC_FILE = ROOT / ".resource-spec.txt"
PORT = "8072"

sys.path.insert(0, str(ROOT / "tools"))
from parseresource import parse as parse_spec, SpecError  # noqa: E402

SQL_TYPE = {"text": "text", "integer": "integer", "real": "real", "boolean": "integer"}
SQL_DEFAULT = {"text": "''", "integer": "0", "real": "0.0", "boolean": "0"}
PY_ARGTYPE = {"integer": ", type=int", "real": ", type=float", "boolean": ", type=int"}
SAMPLE = {"text": '"sample"', "integer": "1", "real": "1.5", "boolean": "1"}
SAMPLE_TEXT = {"text": "sample", "integer": "1", "real": "1.5", "boolean": "1"}


def read_spec():
    if not SPEC_FILE.exists():
        raise SpecError(".resource-spec.txt does not exist yet")
    return parse_spec(SPEC_FILE.read_text())


def next_migration_number():
    d = ROOT / "migrations"
    if not d.is_dir():
        return 1
    used = []
    for p in d.glob("*.sql"):
        m = re.match(r"^(\d+)", p.name)
        if m:
            used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def tokens(name, fields):
    fnames = [f for f, _ in fields]
    return {
        "NAME": name,
        "TITLE": name.replace("_", " ").title(),
        "PORT": PORT,
        "COLUMNS": "\n".join(
            "  %s %s not null default %s," % (f, SQL_TYPE[t], SQL_DEFAULT[t])
            for f, t in fields),
        "FIELD_LIST": ", ".join('"%s"' % f for f in fnames),
        "FIELD_LIST_JS": ", ".join('"%s"' % f for f in fnames),
        "CLI_ARGS": "\n".join(
            '    p.add_argument("--%s"%s, required=True)' % (f, PY_ARGTYPE.get(t, ""))
            for f, t in fields),
        "SAMPLE_JSON": "{" + ", ".join('"%s": %s' % (f, SAMPLE[t]) for f, t in fields) + "}",
        "NEEDLE": '"%s"' % SAMPLE_TEXT[fields[0][1]],
        "NEEDLE_BARE": SAMPLE_TEXT[fields[0][1]],
        "CLI_SAMPLE_ARGS": " ".join(
            "--%s %s" % (f, SAMPLE_TEXT[t]) for f, t in fields),
    }


def render(template_name, toks):
    text = (TEMPLATES / template_name).read_text()
    for key, val in toks.items():
        text = text.replace("{{%s}}" % key, val)
    left = re.findall(r"\{\{([A-Z_]+)\}\}", text)
    if left:
        raise SpecError("template %s has unfilled token(s): %s"
                        % (template_name, ", ".join(sorted(set(left)))))
    return text


# artifact -> (template, output path builder)
ARTIFACTS = {
    "table":         ("table.sql.tmpl",        lambda n: "migrations/%03d_%s.sql" % (next_migration_number(), n)),
    "api-list":      ("api_list.py.tmpl",      lambda n: "api/%s_list.py" % n),
    "api-create":    ("api_create.py.tmpl",    lambda n: "api/%s_create.py" % n),
    "api-get":       ("api_get.py.tmpl",       lambda n: "api/%s_get.py" % n),
    "api-update":    ("api_update.py.tmpl",    lambda n: "api/%s_update.py" % n),
    "api-delete":    ("api_delete.py.tmpl",    lambda n: "api/%s_delete.py" % n),
    "cli-list":      ("cli_list.py.tmpl",      lambda n: "features/%s_list.py" % n),
    "cli-add":       ("cli_add.py.tmpl",       lambda n: "features/%s_add.py" % n),
    "view-list":     ("view_list.js.tmpl",     lambda n: "web/views/%s_list.js" % n),
    "view-form":     ("view_form.js.tmpl",     lambda n: "web/views/%s_form.js" % n),
    "test-roundtrip": ("test_roundtrip.sh.tmpl", lambda n: "tests/%s_roundtrip.sh" % n),
    "test-cli":      ("test_cli.sh.tmpl",      lambda n: "tests/%s_cli.sh" % n),
}


def emit(artifact):
    name, fields = read_spec()
    tmpl, pathfn = ARTIFACTS[artifact]
    rel = pathfn(name)
    out = ROOT / rel
    # a table migration already applied must never be rewritten under a new
    # number -- that would re-run a CREATE TABLE that already exists
    if artifact == "table":
        existing = list((ROOT / "migrations").glob("*_%s.sql" % name)) if (ROOT / "migrations").is_dir() else []
        if existing:
            print("ok   %s already has a migration (%s); nothing to do"
                  % (name, existing[0].name))
            return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(tmpl, tokens(name, fields)))
    print("wrote %s" % rel)
    return 0


def selftest():
    """Render every template against a sample spec and validate each output."""
    import subprocess
    import tempfile
    import sqlite3
    name, fields = parse_spec("widget: label:text, qty:integer, price:real, done:boolean")
    toks = tokens(name, fields)
    problems = 0
    for artifact, (tmpl, pathfn) in sorted(ARTIFACTS.items()):
        try:
            text = render(tmpl, toks)
        except Exception as e:
            print("FAIL %-14s render: %s" % (artifact, e))
            problems += 1
            continue
        suffix = pathlib.Path(tmpl).suffixes[0]
        ok, why = True, ""
        if suffix == ".py":
            try:
                compile(text, tmpl, "exec")
            except SyntaxError as e:
                ok, why = False, "python syntax: %s" % e
        elif suffix == ".sh":
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
                fh.write(text)
                tmp = fh.name
            r = subprocess.run(["sh", "-n", tmp], capture_output=True, text=True)
            ok, why = r.returncode == 0, "sh -n: " + (r.stderr or "").strip()
            pathlib.Path(tmp).unlink()
        elif suffix == ".sql":
            try:
                con = sqlite3.connect(":memory:")
                con.executescript(text)
                con.close()
            except sqlite3.Error as e:
                ok, why = False, "sqlite: %s" % e
        elif suffix == ".js":
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
                fh.write(text)
                tmp = fh.name
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            pathlib.Path(tmp).unlink()
            if r.returncode != 0:
                ok, why = False, "node --check: " + (r.stderr or "").strip().splitlines()[-1]
        print(("ok   " if ok else "FAIL ") + "%-14s -> %s%s"
              % (artifact, pathfn(name), "" if ok else "  " + why))
        if not ok:
            problems += 1
    print("%d artifact(s), %d problem(s)" % (len(ARTIFACTS), problems))
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description="usage: render resource files from templates")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate resource.spec")
    e = sub.add_parser("emit", help="render one artifact")
    e.add_argument("artifact", choices=sorted(ARTIFACTS))
    sub.add_parser("selftest", help="render every template and validate the output")
    args = ap.parse_args()

    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "check":
            name, fields = read_spec()
            print("ok   %s(%s)" % (name, ", ".join("%s:%s" % f for f in fields)))
            return 0
        return emit(args.artifact)
    except SpecError as e:
        print("FAIL %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
