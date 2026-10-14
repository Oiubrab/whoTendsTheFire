#!/usr/bin/env python3
"""Build a script out of blocks, from a plan.

A plan is `.compose-plan.txt`, one operation per line, in a closed grammar:

    newfile PATH skeleton=py_module doc="what this module is for"
    newfile PATH skeleton=cli_command command=NAME help="..." [doc="..."]
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
    python3 tools/compose.py verify             # run every command the plan built
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
SKELETONS = {
    # skeleton: (required keys, optional keys)
    "py_module": ((), ("doc",)),
    "cli_command": (("command", "help"), ("doc",)),
}
COMMAND = re.compile(r"^[a-z][a-z0-9-]*$")
PHASES = ("newfile", "render", "insert", "import")

# constructs and which of their keys may repeat (collected into a list/dict)
CONSTRUCTS = {
    "if_else": logic.if_else,
    "if_elif_else": logic.if_elif_else,
    "for_loop": logic.for_loop,
    "while_loop": logic.while_loop,
    "switch_dispatch": logic.switch_dispatch,
    "logic_gates": lambda spec: logic.logic_gates(),
    "try_fallback": logic.try_fallback,
    "filter_list": logic.filter_list,
    "record": logic.record,
    "count_by": logic.count_by,
    "cli_argument": logic.cli_argument,
    "print_call": logic.print_call,
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
    spec, branches, cases, fields = {}, [], {}, []
    for t in tokens:
        if "=" not in t:
            raise PlanError("line %d: expected key=value, got %r" % (line, t))
        k, v = t.split("=", 1)
        if k == "branch":
            parts = v.split(":", 2)
            if len(parts) != 3:
                raise PlanError("line %d: branch must be OP:LIMIT:LABEL, got %r" % (line, v))
            branches.append(tuple(parts))
        elif k == "field":
            fields.append(v)
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
    if fields:
        spec["fields"] = fields
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
            sk = kv.pop("skeleton", None)
            if sk not in SKELETONS:
                raise PlanError("line %d: skeleton must be one of %s" % (n, ", ".join(sorted(SKELETONS))))
            required, optional = SKELETONS[sk]
            missing = [k for k in required if k not in kv]
            extra = [k for k in kv if k not in required + optional]
            if missing or extra:
                raise PlanError("line %d: skeleton %s needs %s%s" % (
                    n, sk, ", ".join(required) or "no keys",
                    ("; does not take " + ", ".join(extra)) if extra else ""))
            try:
                toks = {"DOC": logic.label(kv.get("doc", "generated module"), "doc")}
                if sk == "cli_command":
                    if not COMMAND.match(kv["command"]):
                        raise PlanError("line %d: command %r must be lowercase letters, digits, hyphens" % (n, kv["command"]))
                    toks["COMMAND"] = kv["command"]
                    toks["HELP"] = logic.label(kv["help"], "help")
            except logic.LogicError as e:
                raise PlanError("line %d: %s" % (n, e))
            path = safe_path(tok[1], n)
            if not path.endswith(".py"):
                raise PlanError("line %d: a python skeleton must be written to a .py path" % n)
            ops.append(dict(op="newfile", path=path, skeleton=sk, toks=toks, line=n))
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


def slot_indents(text):
    found = {}
    for l in text.splitlines():
        m = slot.MARKER.match(l)
        if m:
            found[m.group("name")] = m.group("indent")
    return found


def skeleton_text(name):
    return (ROOT / "templates" / "skeletons" / ("%s.py.tmpl" % name)).read_text()


def skeleton_slots(name):
    return slot_indents(skeleton_text(name))


def existing_commands(root):
    """Subcommand names already registered by modules in features/."""
    names = set()
    fdir = root / "features"
    if fdir.is_dir():
        for f in fdir.glob("*.py"):
            names.update(re.findall(r'add_parser\(\s*"([^"]+)"', f.read_text(errors="replace")))
    return names


def validate(ops, root=ROOT):
    """Everything checkable without touching a file: references and slots."""
    created, commands = {}, set()
    taken = existing_commands(root)
    for o in ops:
        if o["op"] != "newfile":
            continue
        if o["path"] in created:
            raise PlanError("line %d: %s is created twice" % (o["line"], o["path"]))
        if (root / o["path"]).exists():
            raise PlanError("line %d: %s already exists -- newfile only creates" % (o["line"], o["path"]))
        created[o["path"]] = skeleton_slots(o["skeleton"])
        cmd = o["toks"].get("COMMAND")
        if cmd:
            if cmd in taken:
                raise PlanError("line %d: a command called %r already exists in features/" % (o["line"], cmd))
            if cmd in commands:
                raise PlanError("line %d: command %r is created twice in this plan" % (o["line"], cmd))
            commands.add(cmd)
    rendered, kinds = {}, {}
    for o in ops:
        if o["op"] == "render":
            if o["name"] in rendered:
                raise PlanError("line %d: block %r rendered twice" % (o["line"], o["name"]))
            try:  # a real render, so a bad spec is caught now, not mid-apply
                rendered[o["name"]] = CONSTRUCTS[o["construct"]](o["spec"])
                kinds[o["name"]] = o["construct"]
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
                have = slot_indents(target.read_text())
            else:
                raise PlanError("line %d: %s does not exist and no newfile creates it" % (o["line"], path))
            want = o["slot"] if o["op"] == "insert" else "imports"
            if want not in have and not (o["op"] == "import" and path.endswith(".py")):
                raise PlanError("line %d: %s has no slot %r (it has: %s)"
                                % (o["line"], path, want, ", ".join(sorted(have)) or "none"))
            if o["op"] == "insert":
                # placement is law: a statement belongs only in the slot whose
                # names it uses; a whole definition only at module level
                c = kinds[o["name"]]
                indented = have[want] != ""
                if c in logic.STATEMENT_SLOTS:
                    if want not in logic.STATEMENT_SLOTS[c] or not indented:
                        raise PlanError("line %d: a %s block only goes in slot %s inside a command"
                                        % (o["line"], c, "/".join(sorted(logic.STATEMENT_SLOTS[c]))))
                elif indented:
                    raise PlanError("line %d: a %s block is a whole definition; slot %r is inside a function"
                                    % (o["line"], c, want))
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
            text = skeleton_text(o["skeleton"])
            for k, v in o["toks"].items():
                text = text.replace("{{%s}}" % k, v)
            target.write_text(text)
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
    if phase == "import":
        # the imports a block needs follow it into whatever file it landed
        # in -- implied by the block, never something the plan has to list
        by_name = {o["name"]: o for o in ops if o["op"] == "render"}
        for o in ops:
            if o["op"] == "insert":
                r = by_name[o["name"]]
                for line_text in logic.imports_for(r["construct"], r["spec"]):
                    done += 1 if slot.ensure_line(root / o["path"], line_text) else 0
    return done


def load(root=ROOT):
    p = root / PLAN
    if not p.exists():
        raise PlanError("no %s was written" % PLAN)
    return parse(p.read_text())


def verify_commands(ops, root=ROOT):
    """Every command this plan created must load and answer --help."""
    import subprocess
    cmds = [(o["path"], o["toks"]["COMMAND"]) for o in ops
            if o["op"] == "newfile" and o["skeleton"] == "cli_command"]
    if not cmds:
        return ["ok   no commands in this plan -- compile is the whole check"], True
    if not (root / "cli.py").exists():
        return ["FAIL the plan builds commands but there is no cli.py to run them"], False
    out, ok = [], True
    top = subprocess.run([sys.executable, "cli.py", "--help"], cwd=str(root),
                         capture_output=True, text=True, timeout=60)
    for path, cmd in cmds:
        mod = pathlib.Path(path).stem
        if ("skipping %s" % mod) in top.stderr:
            out.append("FAIL %s did not load: %s" % (path, top.stderr.strip()[-300:]))
            ok = False
            continue
        r = subprocess.run([sys.executable, "cli.py", cmd, "--help"], cwd=str(root),
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or "usage" not in r.stdout.lower():
            out.append("FAIL `cli.py %s --help` failed: %s" % (cmd, (r.stderr or r.stdout).strip()[-300:]))
            ok = False
        else:
            out.append("ok   cli.py %s loads and answers --help" % cmd)
    return out, ok


def verify_cli():
    try:
        ops = load()
    except PlanError as e:
        print("FAIL %s" % e)
        return 1
    lines, ok = verify_commands(ops)
    print("\n".join(lines))
    return 0 if ok else 1


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

    cmd_plan = '''
newfile features/grade_cmd.py skeleton=cli_command command=grade help="grade a score" doc="grade, built from blocks"
render if_elif_else as grader func=grade arg=score default=F branch=">=:90:A" branch=">=:80:B"
render record as reading name=Reading field=sensor:str field=value:float field=ok:bool:True
render cli_argument as score_arg name=score type=int help="the score to grade"
render print_call as show func=grade args=score
insert grader into features/grade_cmd.py slot=helpers
insert reading into features/grade_cmd.py slot=helpers
insert score_arg into features/grade_cmd.py slot=arguments
insert show into features/grade_cmd.py slot=body
'''
    import shutil
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        shutil.copy(ROOT / "cli.py", d / "cli.py")
        (d / "features").mkdir()
        (d / "features" / "__init__.py").write_text("")
        ops = parse(cmd_plan)
        validate(ops, d)
        for ph in PHASES:
            apply_phase(ph, ops, d)
        text = (d / "features" / "grade_cmd.py").read_text()
        lines, ok = verify_commands(ops, d)
        expect("verify: the command the plan built loads and answers --help", ok, " / ".join(lines))
        r = subprocess.run([sys.executable, "cli.py", "grade", "85"], cwd=str(d), capture_output=True, text=True)
        expect("`cli.py grade 85` prints B through the real dispatcher", r.stdout.strip() == "B", r.stdout + r.stderr)
        expect("the record's import was implied, not listed", "from dataclasses import dataclass" in text)
        refuses("a command name already taken", cmd_plan.replace("grade_cmd.py", "other.py"), setup=lambda t: (
            (t / "features").mkdir(), (t / "features" / "x.py").write_text('sub.add_parser("grade")')))

    refuses("a definition put inside a function",
            "newfile c.py skeleton=cli_command command=go help=h\nrender logic_gates as g\ninsert g into c.py slot=body")
    refuses("an argument put outside register()",
            "newfile c.py skeleton=cli_command command=go help=h\nrender cli_argument as a name=n type=int help=h\ninsert a into c.py slot=helpers")
    refuses("a print_call put in the arguments slot",
            "newfile c.py skeleton=cli_command command=go help=h\nrender print_call as s func=f\ninsert s into c.py slot=arguments")
    refuses("a command skeleton without its help", "newfile c.py skeleton=cli_command command=go")
    refuses("a newfile over an existing file", "newfile a.py skeleton=py_module",
            setup=lambda t: (t / "a.py").write_text("x = 1\n"))
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
    if argv[:1] == ["verify"]:
        return verify_cli()
    if argv[:1] == ["apply"] and len(argv) == 2:
        return apply_cli(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
