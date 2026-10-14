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
