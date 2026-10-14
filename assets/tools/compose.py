#!/usr/bin/env python3
"""Build a script out of blocks, from a plan.

A plan is `.compose-plan.txt`, one operation per line, in a closed grammar:

    newfile PATH skeleton=py_module doc="what this module is for"
    render CONSTRUCT as NAME key=value key=value ...
    insert NAME into PATH slot=SLOT
    import "LINE" into PATH

    render if_elif_else as grader func=grade arg=score default=F \\
           branch=">=:90:A" branch=">=:80:B" branch=">=:70:C"
    render switch_dispatch as colours func=describe key=code default=unknown \\
           case=r:red case=g:green
    insert grader into features/grading.py slot=body

This is the whole of what a model is asked to decide: which blocks, what to
call things, where they go. How an if or a loop is shaped lives in the
templates (tools/logic.py); where a block lands is decided by the slot
marker in the target (tools/slot.py). Nothing here writes a line of code.

The work is cut into four tiny phases that always run in this order, one
torch each, so a plan can never insert a block before it exists:

    newfile -> render -> insert -> import

Every phase is idempotent, so re-running a torch changes nothing.

    python3 tools/compose.py check              # is the plan well-formed?
    python3 tools/compose.py apply PHASE        # newfile|render|insert|import
    python3 tools/compose.py --check            # self-test
"""

import pathlib
import re
import shlex
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import logic  # noqa: E402
import slot  # noqa: E402

PLAN = ".compose-plan.txt"
SNIPPETS = ".compose"
SKELETONS = ("py_module",)
PHASES = ("newfile", "render", "insert", "import")

# constructs and which of their keys may repeat (collected into a list/dict)
CONSTRUCTS = {
    "if_else": logic.if_else,
    "if_elif_else": logic.if_elif_else,
    "for_loop": logic.for_loop,
    "while_loop": logic.while_loop,
    "switch_dispatch": logic.switch_dispatch,
    "logic_gates": lambda spec: logic.logic_gates(),
}
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class PlanError(Exception):
    pass


def safe_path(p, line):
    if not p or p.startswith("/") or ".." in pathlib.PurePosixPath(p).parts:
        raise PlanError("line %d: path %r must be relative and stay inside the project" % (line, p))
    if p.startswith(".") and not p.startswith("./"):
        raise PlanError("line %d: path %r points at a hidden file" % (line, p))
    return p


def keyvals(tokens, line):
    spec, branches, cases = {}, [], {}
    for t in tokens:
        if "=" not in t:
            raise PlanError("line %d: expected key=value, got %r" % (line, t))
        k, v = t.split("=", 1)
        if k == "branch":
            parts = v.split(":", 2)
            if len(parts) != 3:
                raise PlanError("line %d: branch must be OP:LIMIT:LABEL, got %r" % (line, v))
            branches.append(tuple(parts))
        elif k == "case":
            if ":" not in v:
                raise PlanError("line %d: case must be KEY:TEXT, got %r" % (line, v))
            ck, cv = v.split(":", 1)
            if ck in cases:
                raise PlanError("line %d: case %r given twice" % (line, ck))
            cases[ck] = cv
        else:
            if k in spec:
                raise PlanError("line %d: %s given twice" % (line, k))
            spec[k] = v
    if branches:
        spec["branches"] = branches
    if cases:
        spec["cases"] = cases
    return spec


def parse(text):
    ops = []
    for n, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            tok = shlex.split(raw)
        except ValueError as e:
            raise PlanError("line %d: %s" % (n, e))
        verb = tok[0]
        if verb == "newfile":
            if len(tok) < 3:
                raise PlanError("line %d: newfile PATH skeleton=NAME [doc=TEXT]" % n)
            kv = keyvals(tok[2:], n)
            if kv.get("skeleton") not in SKELETONS:
                raise PlanError("line %d: skeleton must be one of %s" % (n, ", ".join(SKELETONS)))
            doc = logic.label(kv.get("doc", "generated module"), "doc")
            ops.append(dict(op="newfile", path=safe_path(tok[1], n), skeleton=kv["skeleton"], doc=doc, line=n))
        elif verb == "render":
            if len(tok) < 4 or tok[2] != "as":
                raise PlanError("line %d: render CONSTRUCT as NAME key=value ..." % n)
            construct, name = tok[1], tok[3]
            if construct not in CONSTRUCTS:
                raise PlanError("line %d: unknown construct %r (have: %s)" % (n, construct, ", ".join(sorted(CONSTRUCTS))))
            if not NAME.match(name):
                raise PlanError("line %d: block name %r must be lowercase letters, digits, underscore" % (n, name))
            ops.append(dict(op="render", construct=construct, name=name, spec=keyvals(tok[4:], n), line=n))
        elif verb == "insert":
            if len(tok) != 5 or tok[2] != "into" or not tok[4].startswith("slot="):
                raise PlanError("line %d: insert NAME into PATH slot=SLOT" % n)
            ops.append(dict(op="insert", name=tok[1], path=safe_path(tok[3], n), slot=tok[4][5:], line=n))
        elif verb == "import":
            if len(tok) != 4 or tok[2] != "into":
                raise PlanError('line %d: import "LINE" into PATH' % n)
            line_text = tok[1].strip()
            if not re.match(r"^(import [A-Za-z_][\w.]*( as \w+)?|from [A-Za-z_][\w.]* import [\w, *]+)$", line_text):
                raise PlanError("line %d: %r is not a plain import statement" % (n, line_text))
            ops.append(dict(op="import", line_text=line_text, path=safe_path(tok[3], n), line=n))
        else:
            raise PlanError("line %d: unknown operation %r (newfile, render, insert, import)" % (n, verb))
    if not ops:
        raise PlanError("the plan is empty")
    return ops


def skeleton_slots(name):
    text = (ROOT / "templates" / "skeletons" / ("%s.py.tmpl" % name)).read_text()
    found = set()
    for l in text.splitlines():
        m = slot.MARKER.match(l)
        if m:
            found.add(m.group("name"))
    return found


def validate(ops, root=ROOT):
    """Everything checkable without touching a file: references and slots."""
    created = {o["path"]: skeleton_slots(o["skeleton"]) for o in ops if o["op"] == "newfile"}
    rendered = {}
    for o in ops:
        if o["op"] == "render":
            if o["name"] in rendered:
                raise PlanError("line %d: block %r rendered twice" % (o["line"], o["name"]))
            try:  # a real render, so a bad spec is caught now, not mid-apply
                rendered[o["name"]] = CONSTRUCTS[o["construct"]](o["spec"])
            except logic.LogicError as e:
                raise PlanError("line %d: %s" % (o["line"], e))
    for o in ops:
        if o["op"] in ("insert", "import"):
            path = o["path"]
            if o["op"] == "insert" and o["name"] not in rendered:
                raise PlanError("line %d: nothing rendered as %r before this insert" % (o["line"], o["name"]))
            target = root / path
            if path in created:
                have = created[path]
            elif target.exists():
                have = set(slot.list_slots(target))
            else:
                raise PlanError("line %d: %s does not exist and no newfile creates it" % (o["line"], path))
            want = o["slot"] if o["op"] == "insert" else "imports"
            if want not in have and not (o["op"] == "import" and path.endswith(".py")):
                raise PlanError("line %d: %s has no slot %r (it has: %s)"
                                % (o["line"], path, want, ", ".join(sorted(have)) or "none"))
    return rendered


def apply_phase(phase, ops, root=ROOT):
    snippets = root / SNIPPETS
    done = 0
    for o in ops:
        if o["op"] != phase:
            continue
        if phase == "newfile":
            target = root / o["path"]
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            text = (ROOT / "templates" / "skeletons" / ("%s.py.tmpl" % o["skeleton"])).read_text()
            target.write_text(text.replace("{{DOC}}", o["doc"]))
            done += 1
        elif phase == "render":
            snippets.mkdir(exist_ok=True)
            (snippets / ("%s.snippet" % o["name"])).write_text(CONSTRUCTS[o["construct"]](o["spec"]))
            done += 1
        elif phase == "insert":
            snip = snippets / ("%s.snippet" % o["name"])
            if not snip.exists():
                raise PlanError("block %r was never rendered -- run the render phase first" % o["name"])
            done += 1 if slot.insert(root / o["path"], o["slot"], snip.read_text()) else 0
        elif phase == "import":
            done += 1 if slot.ensure_line(root / o["path"], o["line_text"]) else 0
    return done


def load(root=ROOT):
    p = root / PLAN
    if not p.exists():
        raise PlanError("no %s was written" % PLAN)
    return parse(p.read_text())


def check_cli():
    try:
        ops = load()
        validate(ops)
    except (PlanError, slot.SlotError) as e:
        print("FAIL %s" % e)
        return 1
    kinds = {k: sum(1 for o in ops if o["op"] == k) for k in PHASES}
    print("ok   %d operation(s): %s" % (len(ops), ", ".join("%d %s" % (v, k) for k, v in kinds.items() if v)))
    return 0


def apply_cli(phase):
    if phase not in PHASES:
        print("FAIL phase must be one of %s" % ", ".join(PHASES))
        return 2
    try:
        ops = load()
        validate(ops)
        n = apply_phase(phase, ops)
    except (PlanError, slot.SlotError) as e:
        print("FAIL %s" % e)
        return 1
    print("ok   %s: %d change(s)" % (phase, n))
    return 0


def selftest():
    import os
    fails = 0

    def expect(label, cond, extra=""):
        nonlocal fails
        print(("ok   " if cond else "FAIL ") + label + ((" -- " + extra) if (extra and not cond) else ""))
        fails += 0 if cond else 1

    def refuses(label, plan, setup=None):
        nonlocal fails
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            if setup:
                setup(d)
            try:
                validate(parse(plan), d)
                print("FAIL refuses %s (accepted)" % label)
                fails += 1
            except (PlanError, slot.SlotError):
                print("ok   refuses %s" % label)

    good = '''
newfile features/grading.py skeleton=py_module doc="grading helpers"
render if_elif_else as grader func=grade arg=score default=F branch=">=:90:A" branch=">=:80:B" branch=">=:70:C"
render switch_dispatch as colours func=describe key=code default=unknown case=r:red case=g:green
render logic_gates as gates
import "import os" into features/grading.py
insert grader into features/grading.py slot=body
insert colours into features/grading.py slot=body
insert gates into features/grading.py slot=body
'''
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        ops = parse(good)
        validate(ops, d)
        for ph in PHASES:
            apply_phase(ph, ops, d)
        out = d / "features" / "grading.py"
        ns = {}
        exec(compile(out.read_text(), "grading", "exec"), ns)
        expect("the plan builds a module that runs", callable(ns.get("grade")))
        expect("if/elif block works", [ns["grade"](95), ns["grade"](75), ns["grade"](3)] == ["A", "C", "F"])
        expect("switch block works", ns["describe"]("g") == "green" and ns["describe"]("x") == "unknown")
        expect("gate block works", ns["XOR"](True, False) is True)
        expect("the import landed under the imports slot", "import os" in out.read_text())
        before = out.read_text()
        for ph in PHASES:
            apply_phase(ph, ops, d)
        expect("running every phase again changes nothing", out.read_text() == before)

    refuses("an unknown operation", "frobnicate x")
    refuses("an unknown construct", "render quantum_loop as q")
    refuses("a path that escapes the project", 'newfile ../evil.py skeleton=py_module')
    refuses("an absolute path", 'newfile /etc/x.py skeleton=py_module')
    refuses("an unknown skeleton", 'newfile a.py skeleton=rust_crate')
    refuses("an insert of a block never rendered", "newfile a.py skeleton=py_module\ninsert nope into a.py slot=body")
    refuses("an insert into a missing slot",
            "newfile a.py skeleton=py_module\nrender logic_gates as g\ninsert g into a.py slot=nowhere")
    refuses("an insert into a file nothing creates", "render logic_gates as g\ninsert g into ghost.py slot=body")
    refuses("a statement smuggled in as a value",
            "newfile a.py skeleton=py_module\nrender if_else as b func=f arg=x op=> limit=\"1: import os\" then=a else=b\ninsert b into a.py slot=body")
    refuses("a non-import passed as an import", 'newfile a.py skeleton=py_module\nimport "os.system(1)" into a.py')
    refuses("the same block rendered twice", "render logic_gates as g\nrender logic_gates as g")
    refuses("an empty plan", "# nothing\n")
    print("%d failure(s)" % fails)
    return 1 if fails else 0


def main(argv):
    if argv[:1] == ["--check"]:
        return selftest()
    if argv[:1] == ["check"]:
        return check_cli()
    if argv[:1] == ["apply"] and len(argv) == 2:
        return apply_cli(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
