#!/usr/bin/env python3
"""Deterministic cleanup. No model, no judgement, no options.

Every transform here has exactly one correct output for a given input,
which is the definition of law in this project: if there were two
defensible answers it would belong in a decision torch instead.

  - trailing whitespace stripped
  - tabs in leading indentation converted to four spaces
  - exactly one newline at end of file
  - runs of three or more blank lines collapsed to two
  - unused `import x` / `from x import y` statements removed

The import removal is the interesting one, and it is still law: a name
bound by an import and referenced nowhere in the module's syntax tree is
dead by definition. Anything ambiguous is deliberately left alone --
star imports, conditional imports inside try/except, and any module
whose text mentions the name in a string are all skipped rather than
guessed at.

    python3 tools/tidy.py             # rewrite in place, report
    python3 tools/tidy.py --check     # report only, exit 1 if work remains
"""

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "quarantine"}
# removing an import from these would change what the package exports
NEVER_PRUNE = {"__init__.py"}


def targets():
    for p in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.parent.name == "tools":
            continue
        yield p


def whitespace(text):
    lines = [ln.rstrip() for ln in text.split("\n")]
    out = []
    for ln in lines:
        stripped = ln.lstrip("\t")
        tabs = len(ln) - len(stripped)
        out.append("    " * tabs + stripped if tabs else ln)
    # collapse 3+ blank lines to 2
    collapsed = []
    blanks = 0
    for ln in out:
        if ln == "":
            blanks += 1
            if blanks > 2:
                continue
        else:
            blanks = 0
        collapsed.append(ln)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return "\n".join(collapsed) + "\n" if collapsed else ""


def bound_names(node):
    """(line, {name: asname}) for one import statement, or None if unsafe."""
    names = {}
    for a in node.names:
        if a.name == "*":
            return None
        local = a.asname or a.name.split(".")[0]
        names[local] = a
    return names


def used_names(tree, skip):
    """Every identifier the module refers to, ignoring the import rows given."""
    used = set()
    for node in ast.walk(tree):
        if node in skip:
            continue
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # a.b.c -- walk down to the root Name, which ast.walk also
            # visits, so this is belt and braces for dotted module use
            cur = node
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                used.add(cur.id)
    return used


def in_try(tree, stmt):
    """True if stmt sits inside a try block -- a guarded optional import."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                if child is stmt:
                    return True
    return False


def prune_imports(path, text):
    """Return (new_text, [removed descriptions])."""
    if path.name in NEVER_PRUNE:
        return text, []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, []

    imports = [n for n in ast.walk(tree)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not imports:
        return text, []

    nodes = set()
    for n in imports:
        for sub in ast.walk(n):
            nodes.add(sub)
    used = used_names(tree, nodes)

    # any name appearing inside a string literal anywhere is treated as
    # possibly-referenced: getattr, __import__, doctest and type
    # annotations in quotes all do this, and a wrong removal is far
    # worse than a missed one.
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for word in node.value.replace(".", " ").replace("(", " ").split():
                used.add(word.strip("'\"[]{},:"))

    drop_lines = set()
    removed = []
    for n in imports:
        if in_try(tree, n):
            continue
        names = bound_names(n)
        if names is None:
            continue
        if any(local in used for local in names):
            continue
        if n.end_lineno != n.lineno:
            continue  # multi-line import: leave it to a human
        drop_lines.add(n.lineno)
        label = ", ".join(sorted(names))
        removed.append("%s:%d  %s" % (path.name, n.lineno, label))

    if not drop_lines:
        return text, []
    lines = text.split("\n")
    kept = [ln for i, ln in enumerate(lines, start=1) if i not in drop_lines]
    return "\n".join(kept), removed


def main():
    check = "--check" in sys.argv
    changed, removed_all = [], []
    for p in targets():
        original = p.read_text(encoding="utf-8", errors="replace")
        text, removed = prune_imports(p, original)
        text = whitespace(text)
        # a prune can leave the file unparseable only if the input was
        # already broken; verify anyway and back out if so.
        if text != original:
            try:
                ast.parse(text)
            except SyntaxError:
                continue
            changed.append(str(p.relative_to(ROOT)))
            removed_all.extend(removed)
            if not check:
                p.write_text(text, encoding="utf-8")

    for r in removed_all:
        print("removed unused import  " + r)
    for c in changed:
        print(("would tidy " if check else "tidied ") + c)
    if not changed:
        print("nothing to tidy")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
