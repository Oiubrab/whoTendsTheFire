#!/usr/bin/env python3
"""Render the basic logic constructs from assets/templates/logic/.

Same convention as resource.py: `{{KEY}}` placeholders, filled by plain
substitution. The point of this file is the division of labour. The shape
of an if/else, a loop or a switch is law -- it was settled decades ago and
lives in the template. What is left to choose is small and nameable: what
to call the function, which operator, which limit, which labels. Variable
length pieces (how many elif branches, how many switch cases) are expanded
here by code, so nothing about structure is ever left to a model.

    python3 tools/logic.py                 # render every example to stdout
    python3 tools/logic.py --check         # render each, EXECUTE it, assert
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "logic"

COMPARE_OPS = {"<", "<=", ">", ">=", "==", "!="}
ACC_OPS = {"+=", "-=", "*=", "|=", "&="}
STEP_OPS = {"+", "-", "*"}


class LogicError(Exception):
    pass


# Everything a spec supplies ends up pasted into source code, so every value
# is checked against what its position in the template can safely hold. The
# first version trusted its inputs, which is fine for a hand-written example
# and wrong the moment a model supplies them: a limit of `1: import os`
# renders into a different program, and a label containing a quote renders
# into a syntax error.
import keyword
import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# small arithmetic expressions over names and numbers: no quotes, no
# colons, no semicolons, no newlines, so no way to start a new statement
_EXPR = re.compile(r"^[A-Za-z0-9_.+\-*/%() \[\]]+$")
_LABEL_BAD = re.compile(r'["\\\n\r{}]')


def ident(value, what):
    v = str(value)
    if not _IDENT.match(v) or keyword.iskeyword(v):
        raise LogicError("%s %r is not a usable python name" % (what, v))
    return v


def expr(value, what):
    v = str(value)
    if not _EXPR.match(v) or v.strip() != v or "  " in v:
        raise LogicError("%s %r is not a plain arithmetic expression" % (what, v))
    if v.count("(") != v.count(")") or v.count("[") != v.count("]"):
        raise LogicError("%s %r has unbalanced brackets" % (what, v))
    return v


def label(value, what):
    v = str(value)
    if not v or _LABEL_BAD.search(v):
        raise LogicError("%s %r must be non-empty text with no quotes, backslashes, braces or newlines" % (what, v))
    return v


def render(name, toks):
    text = (TEMPLATES / name).read_text()
    for key, val in toks.items():
        text = text.replace("{{%s}}" % key, str(val))
    if "{{" in text:
        left = text[text.index("{{"):].split("}}")[0] + "}}"
        raise LogicError("%s: unfilled placeholder %s" % (name, left))
    return text


def need(spec, *keys):
    missing = [k for k in keys if k not in spec]
    if missing:
        raise LogicError("spec missing: %s" % ", ".join(missing))


def one_of(value, allowed, what):
    if value not in allowed:
        raise LogicError("%s %r is not one of %s" % (what, value, sorted(allowed)))
    return value


def if_else(spec):
    need(spec, "func", "arg", "op", "limit", "then", "else")
    return render("if_else.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"), "ARG": ident(spec["arg"], "argument"),
        "OP": one_of(spec["op"], COMPARE_OPS, "operator"),
        "LIMIT": expr(spec["limit"], "limit"),
        "THEN_LABEL": label(spec["then"], "then label"),
        "ELSE_LABEL": label(spec["else"], "else label"),
    })


def if_elif_else(spec):
    """branches: [(op, limit, label), ...] tried in order."""
    need(spec, "func", "arg", "branches", "default")
    if not spec["branches"]:
        raise LogicError("an if/elif chain needs at least one branch")
    arg = ident(spec["arg"], "argument")
    lines = []
    for i, (op, limit, text) in enumerate(spec["branches"]):
        kw = "if" if i == 0 else "elif"
        one_of(op, COMPARE_OPS, "operator")
        lines.append("    %s %s %s %s:" % (kw, arg, op, expr(limit, "branch limit")))
        lines.append('        return "%s"' % label(text, "branch label"))
    return render("if_elif_else.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"), "ARG": arg,
        "BRANCHES": "\n".join(lines),
        "DEFAULT_LABEL": label(spec["default"], "default label"),
    })


def for_loop(spec):
    need(spec, "func", "collection", "item", "acc", "acc_start", "acc_op", "item_expr", "verb")
    return render("for_loop.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"),
        "COLLECTION": ident(spec["collection"], "collection"),
        "ITEM": ident(spec["item"], "item"), "ACC": ident(spec["acc"], "accumulator"),
        "ACC_START": expr(spec["acc_start"], "accumulator start"),
        "ACC_OP": one_of(spec["acc_op"], ACC_OPS, "accumulator operator"),
        "ITEM_EXPR": expr(spec["item_expr"], "item expression"),
        "ACCUMULATE_VERB": label(spec["verb"], "verb"),
    })


def while_loop(spec):
    need(spec, "func", "start", "continue_op", "bound", "step_op", "step")
    return render("while_loop.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"), "START": ident(spec["start"], "counter"),
        "CONTINUE_OP": one_of(spec["continue_op"], COMPARE_OPS, "operator"),
        "BOUND": expr(spec["bound"], "bound"),
        "STEP_OP": one_of(spec["step_op"], STEP_OPS, "step operator"),
        "STEP": expr(spec["step"], "step"),
    })


def switch_dispatch(spec):
    """cases: {key: returned_text}; one tiny handler is generated per case."""
    need(spec, "func", "key", "cases", "default")
    if not spec["cases"]:
        raise LogicError("a switch needs at least one case")
    handlers, rows, seen = [], [], set()
    for case_key, text in spec["cases"].items():
        case_key = label(case_key, "case key")
        slug = "".join(c if c.isalnum() else "_" for c in case_key).lower()
        h = "_on_%s" % slug
        if h in seen:
            raise LogicError("case key %r collides with another case once made a name" % case_key)
        seen.add(h)
        handlers.append('def %s():\n    return "%s"\n' % (h, label(text, "case text")))
        rows.append('    "%s": %s,' % (case_key, h))
    handlers.append('def _on_default():\n    return "%s"\n' % label(spec["default"], "default text"))
    return render("switch_dispatch.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"), "KEY": ident(spec["key"], "key argument"),
        "TABLE": "_CASES",
        "HANDLERS": "\n\n".join(h.rstrip("\n") for h in handlers),
        "CASES": "\n".join(rows), "DEFAULT_NAME": "_on_default",
    })


def logic_gates(spec=None):
    return render("logic_gates.py.tmpl", {})


# ---- the second batch: fallbacks, filters, records, counts, and the two
# statement-level blocks that turn a module into a working command ----

# Calls a try/fallback may wrap: a closed set, each carrying the import it
# needs. A model can pick int or json.loads; it cannot pick os.system.
CALLS = {
    "int": None, "float": None, "str": None, "len": None, "abs": None, "round": None,
    "json.loads": "import json",
    "math.sqrt": "import math",
    "statistics.mean": "import statistics",
    "statistics.median": "import statistics",
    "date.fromisoformat": "from datetime import date",
}
EXCEPTIONS = {"ValueError", "TypeError", "KeyError", "IndexError",
              "ZeroDivisionError", "OSError", "AttributeError"}
FIELD_TYPES = {"str", "int", "float", "bool"}
ARG_TYPES = {"str", "int", "float"}
_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_CAPWORDS = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def literal(value, typ, what):
    """A default value, checked against the type it has to be."""
    v = str(value)
    if typ == "str":
        return '"%s"' % label(v, what) if v else '""'
    if typ == "bool":
        if v not in ("True", "False"):
            raise LogicError("%s %r must be True or False" % (what, v))
        return v
    if typ == "int" and re.match(r"^-?\d+$", v):
        return v
    if typ == "float" and _NUM.match(v):
        return v
    raise LogicError("%s %r is not a %s literal" % (what, v, typ))


def try_fallback(spec):
    need(spec, "func", "arg", "call", "exc")
    excs = [e.strip() for e in str(spec["exc"]).split(",") if e.strip()]
    if not excs:
        raise LogicError("name at least one exception to catch")
    for e in excs:
        one_of(e, EXCEPTIONS, "exception")
    if len(set(excs)) != len(excs):
        raise LogicError("exception named twice: %s" % spec["exc"])
    if "fallback_text" in spec:
        fallback = '"%s"' % label(spec["fallback_text"], "fallback text")
    elif str(spec.get("fallback", "None")) in ("None", "True", "False") or _NUM.match(str(spec.get("fallback", ""))):
        fallback = str(spec.get("fallback", "None"))
    else:
        raise LogicError("fallback %r must be a number, None, True, False -- or use fallback_text"
                         % spec.get("fallback"))
    return render("try_fallback.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"), "ARG": ident(spec["arg"], "argument"),
        "CALL": one_of(spec["call"], set(CALLS), "call"),
        "EXC": excs[0] if len(excs) == 1 else "(%s)" % ", ".join(excs),
        "EXC_DOC": " or ".join(excs), "FALLBACK": fallback,
    })


def filter_list(spec):
    need(spec, "func", "collection", "item", "op", "limit")
    return render("filter_list.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"),
        "COLLECTION": ident(spec["collection"], "collection"),
        "ITEM": ident(spec["item"], "item"),
        "OP": one_of(spec["op"], COMPARE_OPS, "operator"),
        "LIMIT": expr(spec["limit"], "limit"),
    })


def record(spec):
    """fields: ["name:type", "name:type:default", ...] in declaration order."""
    need(spec, "name", "fields")
    name = str(spec["name"])
    if not _CAPWORDS.match(name):
        raise LogicError("record name %r must be CapWords, like Habit or Reading" % name)
    if not spec["fields"]:
        raise LogicError("a record needs at least one field")
    lines, seen, defaulted = [], set(), None
    for f in spec["fields"]:
        parts = str(f).split(":", 2)
        if len(parts) < 2:
            raise LogicError("field %r must be name:type or name:type:default" % f)
        fname, ftype = ident(parts[0], "field name"), one_of(parts[1], FIELD_TYPES, "field type")
        if fname in seen:
            raise LogicError("field %r declared twice" % fname)
        seen.add(fname)
        if len(parts) == 3:
            lines.append("    %s: %s = %s" % (fname, ftype, literal(parts[2], ftype, "default for " + fname)))
            defaulted = fname
        else:
            # compile() would accept this; the dataclass decorator refuses it
            # at import time, which is exactly the failure a parse check misses
            if defaulted:
                raise LogicError("field %r has no default but follows %r, which does -- "
                                 "fields with defaults must come last" % (fname, defaulted))
            lines.append("    %s: %s" % (fname, ftype))
    return render("record.py.tmpl", {
        "NAME": name, "DOC": label(spec.get("doc", "One %s." % name), "doc"),
        "FIELDS": "\n".join(lines),
    })


def count_by(spec):
    """Counts the items themselves, or one field of each row if key= is given."""
    need(spec, "func", "collection")
    coll = ident(spec["collection"], "collection")
    if "key" in spec:
        k = label(spec["key"], "key")
        count_expr, what = '_row["%s"] for _row in %s' % (k, coll), k
    else:
        count_expr, what = coll, "item"
    return render("count_by.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"), "COLLECTION": coll,
        "COUNT_EXPR": count_expr, "WHAT": what,
    })


def cli_argument(spec):
    """One argument on a command's parser. Statement-level: needs `p`."""
    need(spec, "name", "type", "help")
    name = ident(spec["name"], "argument name")
    typ = one_of(spec["type"], ARG_TYPES, "argument type")
    optional = str(spec.get("optional", "no")) == "yes"
    if not optional and "default" in spec:
        raise LogicError("a positional argument cannot have a default -- add optional=yes")
    default = ""
    if optional and "default" in spec:
        default = " default=%s," % literal(spec["default"], typ, "default")
    return render("cli_argument.py.tmpl", {
        "FLAG": '"--%s"' % name if optional else '"%s"' % name,
        "TYPE": typ, "DEFAULT": default, "HELP": label(spec["help"], "help"),
    })


def print_call(spec):
    """Call a helper on the parsed arguments and print what it returns."""
    need(spec, "func")
    names = [a.strip() for a in str(spec.get("args", "")).split(",") if a.strip()]
    return render("print_call.py.tmpl", {
        "FUNC": ident(spec["func"], "function name"),
        "CALL_ARGS": ", ".join("args.%s" % ident(a, "argument") for a in names),
    })


# Where each block may go. A whole definition belongs at module level; a
# statement only makes sense in the slot whose names it uses -- `p` exists
# inside register(), `args` inside run(). Checked before anything is written.
STATEMENT_SLOTS = {"cli_argument": {"arguments"}, "print_call": {"body"}}


def imports_for(construct, spec):
    """The import lines a block needs. Law: implied by the block, not chosen."""
    if construct == "try_fallback":
        need_line = CALLS.get(spec.get("call"))
        return [need_line] if need_line else []
    if construct == "record":
        return ["from dataclasses import dataclass"]
    if construct == "count_by":
        return ["from collections import Counter"]
    return []


# one worked example per construct -- what a torch would hand the renderer
EXAMPLES = {
    "if_else": (if_else, dict(func="is_adult", arg="age", op=">=", limit=18,
                              then="adult", **{"else": "minor"})),
    "if_elif_else": (if_elif_else, dict(func="grade", arg="score", default="F",
                                        branches=[(">=", 90, "A"), (">=", 80, "B"), (">=", 70, "C")])),
    "for_loop": (for_loop, dict(func="total", collection="numbers", item="n", acc="result",
                                acc_start=0, acc_op="+=", item_expr="n", verb="summing")),
    "while_loop": (while_loop, dict(func="halvings", start="n", continue_op=">", bound=1,
                                    step_op="-", step=1)),
    "switch_dispatch": (switch_dispatch, dict(func="describe", key="code", default="unknown",
                                              cases={"r": "red", "g": "green", "b": "blue"})),
    "logic_gates": (logic_gates, {}),
    "try_fallback": (try_fallback, dict(func="to_int", arg="text", call="int", exc="ValueError,TypeError", fallback=0)),
    "filter_list": (filter_list, dict(func="passing", collection="scores", item="s", op=">=", limit=50)),
    "record": (record, dict(name="Reading", doc="One sensor reading.",
                            fields=["sensor:str", "value:float", "ok:bool:True"])),
    "count_by": (count_by, dict(func="by_status", collection="rows", key="status")),
    "cli_argument": (cli_argument, dict(name="score", type="int", help="the score to grade")),
    "print_call": (print_call, dict(func="grade", args="score")),
}


def check():
    """Execute every rendered example and assert what it actually does."""
    failures = 0

    def run(name, expect):
        nonlocal failures
        fn, spec = EXAMPLES[name]
        ns = {}
        exec(compile(fn(spec), name, "exec"), ns)
        try:
            expect(ns)
            print("ok   %-16s renders, runs, behaves" % name)
        except AssertionError as e:
            failures += 1
            print("FAIL %-16s %s" % (name, e))

    def t_if_else(ns):
        assert ns["is_adult"](18) == "adult" and ns["is_adult"](17) == "minor"

    def t_chain(ns):
        g = ns["grade"]
        assert [g(95), g(85), g(75), g(10)] == ["A", "B", "C", "F"], "chain order wrong"
        assert g(90) == "A", "boundary must hit the first branch"

    def t_for(ns):
        assert ns["total"]([1, 2, 3, 4]) == 10 and ns["total"]([]) == 0

    def t_while(ns):
        assert ns["halvings"](5) == 4 and ns["halvings"](1) == 0

    def t_switch(ns):
        d = ns["describe"]
        assert d("r") == "red" and d("b") == "blue" and d("zzz") == "unknown"

    def t_gates(ns):
        tt = {g: [r[2] for r in ns["truth_table"](g)] for g in ns["GATES"]}
        assert tt["AND"] == [False, False, False, True], tt["AND"]
        assert tt["OR"] == [False, True, True, True], tt["OR"]
        assert tt["XOR"] == [False, True, True, False], tt["XOR"]
        assert tt["NAND"] == [True, True, True, False], tt["NAND"]
        assert tt["NOR"] == [True, False, False, False], tt["NOR"]
        assert ns["NOT"](True) is False

    run("if_else", t_if_else)
    run("if_elif_else", t_chain)
    run("for_loop", t_for)
    run("while_loop", t_while)
    run("switch_dispatch", t_switch)
    run("logic_gates", t_gates)

    def run_with_imports(name, expect):
        nonlocal failures
        fn, spec = EXAMPLES[name]
        code = "\n".join(imports_for(name, spec)) + "\n" + fn(spec)
        ns = {}
        try:
            exec(compile(code, name, "exec"), ns)
            expect(ns)
            print("ok   %-16s renders, runs, behaves" % name)
        except (AssertionError, Exception) as e:
            failures += 1
            print("FAIL %-16s %s: %s" % (name, type(e).__name__, e))

    def t_try(ns):
        f = ns["to_int"]
        assert f("12") == 12 and f("twelve") == 0 and f(None) == 0, "fallback not taken"

    def t_filter(ns):
        assert ns["passing"]([10, 50, 90]) == [50, 90]

    def t_record(ns):
        r = ns["Reading"]("probe", 1.5)
        assert r.ok is True and r.value == 1.5, "default or field order wrong"

    def t_count(ns):
        rows = [{"status": "done"}, {"status": "open"}, {"status": "done"}]
        assert ns["by_status"](rows) == [("done", 2), ("open", 1)]

    run_with_imports("try_fallback", t_try)
    run_with_imports("filter_list", t_filter)
    run_with_imports("record", t_record)
    run_with_imports("count_by", t_count)

    # the two statement blocks only mean something inside a command, so
    # assemble one around them and actually parse arguments through it
    try:
        import argparse
        ns = {"argparse": argparse, "grade": lambda s: "B" if s >= 80 else "C"}
        p = argparse.ArgumentParser()
        ns["p"] = p
        exec(cli_argument(EXAMPLES["cli_argument"][1]), ns)
        args = p.parse_args(["85"])
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(print_call(EXAMPLES["print_call"][1]), {**ns, "args": args})
        assert args.score == 85 and buf.getvalue().strip() == "B", buf.getvalue()
        p2 = argparse.ArgumentParser()
        exec(cli_argument(dict(name="limit", type="int", help="cap", optional="yes", default=3)), {"p": p2})
        assert p2.parse_args([]).limit == 3 and p2.parse_args(["--limit", "9"]).limit == 9
        print("ok   %-16s parse real arguments and print through a helper" % "cli statements")
    except Exception as e:
        failures += 1
        print("FAIL cli statements %s: %s" % (type(e).__name__, e))

    # the gates a model might get wrong must be REFUSED, not rendered
    for label, call in [
        ("bad operator", lambda: if_else(dict(func="f", arg="x", op="=>", limit=1, then="a", **{"else": "b"}))),
        ("empty chain", lambda: if_elif_else(dict(func="f", arg="x", branches=[], default="d"))),
        ("missing key", lambda: while_loop(dict(func="f"))),
        ("empty switch", lambda: switch_dispatch(dict(func="f", key="k", cases={}, default="d"))),
        ("statement smuggled into a limit", lambda: if_else(dict(func="f", arg="x", op=">", limit="1: import os", then="a", **{"else": "b"}))),
        ("keyword as a name", lambda: if_else(dict(func="class", arg="x", op=">", limit=1, then="a", **{"else": "b"}))),
        ("quote in a label", lambda: if_else(dict(func="f", arg="x", op=">", limit=1, then='a"b', **{"else": "b"}))),
        ("call in an expression slot", lambda: for_loop(dict(func="f", collection="c", item="i", acc="a", acc_start=0, acc_op="+=", item_expr="open('x')", verb="v"))),
        ("two cases that become one name", lambda: switch_dispatch(dict(func="f", key="k", default="d", cases={"a-b": "x", "a_b": "y"}))),
        ("a call outside the allowed set", lambda: try_fallback(dict(func="f", arg="x", call="os.system", exc="OSError"))),
        ("an exception outside the allowed set", lambda: try_fallback(dict(func="f", arg="x", call="int", exc="BaseException"))),
        ("a fallback that is code", lambda: try_fallback(dict(func="f", arg="x", call="int", exc="ValueError", fallback="exit()"))),
        ("a field without a default after one with", lambda: record(dict(name="R", fields=["a:int:1", "b:int"]))),
        ("a lowercase record name", lambda: record(dict(name="reading", fields=["a:int"]))),
        ("a default of the wrong type", lambda: record(dict(name="R", fields=["a:int:hello"]))),
        ("a positional argument with a default", lambda: cli_argument(dict(name="n", type="int", help="h", default=1))),
        ("an argument type outside the set", lambda: cli_argument(dict(name="n", type="list", help="h"))),
    ]:
        try:
            call()
            failures += 1
            print("FAIL refusal: %s was rendered" % label)
        except LogicError:
            print("ok   refuses %s" % label)

    print("%d failure(s)" % failures)
    return 1 if failures else 0


def main():
    if "--check" in sys.argv:
        return check()
    for name, (fn, spec) in EXAMPLES.items():
        print("# ---- %s ----" % name)
        print(fn(spec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
