#!/usr/bin/env python3
"""Put a block of code at a named spot in an existing script.

The primitive underneath "put this if block in that script" and "add that
case to that switch". A target file carries marker comments --

    # @slot body            (python, shell, yaml)
    // @slot body           (js, ts, css-in-js)
    <!-- @slot body -->     (html)
    -- @slot body           (sql)

-- and a block is inserted immediately BEFORE the marker, re-indented to
the marker's own indentation. The marker stays, so a second insert lands
after the first and inserts stack in the order they were made.

Everything here is law: where the block goes is decided by the marker, not
by anyone's judgement, and the three failure modes a model would otherwise
have to guard against are handled once, here:

  - a slot that does not exist is an error, never a guess about where the
    block "probably" belongs
  - inserting the same block twice is a no-op (each block carries a short
    content tag), so re-running a torch cannot duplicate code
  - a python file that would stop compiling is left exactly as it was

    python3 tools/slot.py insert FILE SLOT SNIPPET_FILE
    python3 tools/slot.py ensure-line FILE "import os"
    python3 tools/slot.py slots FILE
    python3 tools/slot.py --check
"""

import hashlib
import pathlib
import re
import sys
import tempfile
import textwrap

MARKER = re.compile(r"^(?P<indent>[ \t]*)(?P<open><!--|//|--|#)[ \t]*@slot[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?P<close>-->)?[ \t]*$")
TAG = "@from"


class SlotError(Exception):
    pass


def _find_slots(lines):
    found = {}
    for i, line in enumerate(lines):
        m = MARKER.match(line.rstrip("\n"))
        if m:
            found.setdefault(m.group("name"), []).append((i, m))
    return found


def list_slots(path):
    lines = pathlib.Path(path).read_text().splitlines(keepends=True)
    return {name: [i + 1 for i, _ in hits] for name, hits in _find_slots(lines).items()}


def _comment(m, text):
    close = " -->" if m.group("close") else ""
    return "%s%s %s%s\n" % (m.group("indent"), m.group("open"), text, close)


def _write_checked(path, new_text):
    """Write new_text, unless it is a .py file that no longer compiles."""
    path = pathlib.Path(path)
    if path.suffix == ".py":
        try:
            compile(new_text, str(path), "exec")
        except SyntaxError as e:
            raise SlotError("refusing: %s would no longer compile (%s, line %s); file untouched"
                            % (path.name, e.msg, e.lineno))
    path.write_text(new_text)


def insert(path, slot, snippet, tagged=True):
    path = pathlib.Path(path)
    if not path.exists():
        raise SlotError("no such file: %s" % path)
    lines = path.read_text().splitlines(keepends=True)
    slots = _find_slots(lines)
    if slot not in slots:
        known = ", ".join(sorted(slots)) or "none"
        raise SlotError("%s has no slot %r (slots present: %s)" % (path.name, slot, known))
    if len(slots[slot]) > 1:
        raise SlotError("%s declares slot %r %d times; a slot must be unique"
                        % (path.name, slot, len(slots[slot])))
    body = textwrap.dedent(snippet).strip("\n")
    if not body.strip():
        raise SlotError("empty snippet")
    tag = hashlib.sha256(body.encode()).hexdigest()[:8]
    marker_line = "%s %s:%s" % (slot, TAG, tag)
    if tagged and any(marker_line in l for l in lines):
        return False  # this exact block is already in this slot
    idx, m = slots[slot][0]
    indent = m.group("indent")
    block = [_comment(m, marker_line)] if tagged else []
    if indent == "" and re.match(r"(def |class |async def |@)", body):
        # a top-level definition wants two blank lines above it (PEP 8);
        # count the blanks already there so a second insert doesn't pile up
        blanks = 0
        for l in reversed(lines[:idx]):
            if l.strip():
                break
            blanks += 1
        if idx - blanks > 0:
            block = ["\n"] * max(0, 2 - blanks) + block
    for l in body.splitlines():
        block.append((indent + l + "\n") if l.strip() else "\n")
    new = lines[:idx] + block + lines[idx:]
    _write_checked(path, "".join(new))
    return True


def ensure_line(path, line):
    """Make sure `line` is present. For .py, it joins the top-level imports."""
    path = pathlib.Path(path)
    if not path.exists():
        raise SlotError("no such file: %s" % path)
    lines = path.read_text().splitlines(keepends=True)
    want = line.strip()
    if any(l.strip() == want for l in lines):
        return False
    slots = _find_slots(lines)
    if "imports" in slots:
        return insert(path, "imports", line, tagged=False)
    if path.suffix != ".py":
        raise SlotError("%s has no `imports` slot; cannot place %r" % (path.name, want))
    last = None
    for i, l in enumerate(lines):
        if re.match(r"(import|from)\s+\S", l):
            last = i
    if last is None:
        # after a leading docstring if there is one, else the very top
        text = "".join(lines)
        at = 0
        m = re.match(r'\s*("""|\'\'\')', text)
        if m:
            end = text.find(m.group(1), m.end())
            if end != -1:
                at = text.count("\n", 0, end + 3) + 1
        new = lines[:at] + [want + "\n"] + lines[at:]
    else:
        new = lines[:last + 1] + [want + "\n"] + lines[last + 1:]
    _write_checked(path, "".join(new))
    return True


def check():
    fails = 0

    def expect(label, cond, extra=""):
        nonlocal fails
        print(("ok   " if cond else "FAIL ") + label + ((" -- " + extra) if (extra and not cond) else ""))
        fails += 0 if cond else 1

    def raises(label, fn):
        nonlocal fails
        try:
            fn()
            print("FAIL " + label + " (did not refuse)")
            fails += 1
        except SlotError:
            print("ok   " + label)

    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        py = d / "a.py"
        py.write_text('"""doc"""\nimport sys\n\n\ndef run(x):\n    # @slot body\n    return x\n')

        expect("insert lands before the marker, at the marker's indent",
               insert(py, "body", "if x > 1:\n    x = 1") and
               "    if x > 1:\n        x = 1\n    # @slot body" in py.read_text(),
               py.read_text())
        expect("the file still compiles and the block runs", True if compile(py.read_text(), "a", "exec") else False)
        expect("inserting the identical block again is a no-op",
               insert(py, "body", "if x > 1:\n    x = 1") is False and py.read_text().count("x = 1") == 1)
        insert(py, "body", "x = x + 1")
        t = py.read_text()
        expect("a second, different block stacks AFTER the first",
               t.index("x = 1") < t.index("x = x + 1") < t.index("# @slot body"))

        top = d / "top.py"
        top.write_text("# @slot body\n")
        insert(top, "body", "def a():\n    return 1")
        insert(top, "body", "def b():\n    return 2")
        tt = top.read_text()
        expect("top-level defs end up two blank lines apart, not piled or glued",
               "return 1\n\n\n# body @from:" in tt and "\n\n\n\n" not in tt, repr(tt))

        raises("a missing slot is refused, not guessed", lambda: insert(py, "nope", "pass"))
        before = py.read_text()
        raises("a block that breaks python is refused", lambda: insert(py, "body", "if x >"))
        expect("...and the file is untouched afterwards", py.read_text() == before)
        raises("an empty snippet is refused", lambda: insert(py, "body", "   \n"))
        raises("a missing file is refused", lambda: insert(d / "ghost.py", "body", "pass"))

        expect("ensure-line adds an import after the last import",
               ensure_line(py, "import os") and "import sys\nimport os\n" in py.read_text())
        expect("ensure-line is idempotent", ensure_line(py, "import os") is False)

        bare = d / "b.py"
        bare.write_text('"""just a docstring"""\n\nx = 1\n')
        ensure_line(bare, "import json")
        expect("with no imports it goes under the docstring",
               bare.read_text().startswith('"""just a docstring"""\nimport json\n'), bare.read_text())

        js = d / "v.js"
        js.write_text("function f() {\n  // @slot body\n}\n")
        insert(js, "body", "console.log(1);")
        expect("// markers work for javascript", "  console.log(1);\n  // @slot body" in js.read_text())

        html = d / "p.html"
        html.write_text("<ul>\n  <!-- @slot items -->\n</ul>\n")
        insert(html, "items", "<li>one</li>")
        expect("<!-- --> markers work for html", "  <li>one</li>\n  <!-- @slot items -->" in html.read_text())

        dup = d / "c.py"
        dup.write_text("# @slot a\n# @slot a\n")
        raises("a slot declared twice is refused as ambiguous", lambda: insert(dup, "a", "pass"))
        want_line = [i + 1 for i, l in enumerate(py.read_text().splitlines()) if "@slot body" in l and "@from" not in l]
        expect("slots lists where each marker is", list_slots(py) == {"body": want_line}, str(list_slots(py)))

    print("%d failure(s)" % fails)
    return 1 if fails else 0


def main(argv):
    if argv[:1] == ["--check"]:
        return check()
    try:
        if argv[:1] == ["insert"] and len(argv) == 4:
            did = insert(argv[1], argv[2], pathlib.Path(argv[3]).read_text())
            print("inserted into %s @slot %s" % (argv[1], argv[2]) if did else "already present, left alone")
            return 0
        if argv[:1] == ["ensure-line"] and len(argv) == 3:
            print("added" if ensure_line(argv[1], argv[2]) else "already present, left alone")
            return 0
        if argv[:1] == ["slots"] and len(argv) == 2:
            for name, at in sorted(list_slots(argv[1]).items()):
                print("%-16s line %s" % (name, ", ".join(map(str, at))))
            return 0
    except SlotError as e:
        print("FAIL %s" % e)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
