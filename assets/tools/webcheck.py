#!/usr/bin/env python3
"""Structural check on web/ -- HTML tag balance and JS bracket balance.

An honest note on what this is and is not: there is no Node in the
sandbox and no network to fetch a parser, so this is not a JavaScript
parser and does not claim to be. It catches the failure that actually
happens when a model writes a view -- an unclosed tag, an unbalanced
brace, a string left open, a script block that ends mid-expression --
and it is deterministic about it. A file that passes here can still be
semantically wrong; a file that fails here is definitely broken.

    python3 tools/webcheck.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr", "!doctype", "!--"}
PAIRS = {")": "(", "]": "[", "}": "{"}
OPENERS = set(PAIRS.values())


def js_balance(text, label):
    """Bracket balance outside strings and comments. Returns list of errors."""
    errs = []
    stack = []
    i, n = 0, len(text)
    line = 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        # comments
        if c == "/" and i + 1 < n:
            if text[i + 1] == "/":
                j = text.find("\n", i)
                i = n if j < 0 else j
                continue
            if text[i + 1] == "*":
                j = text.find("*/", i + 2)
                if j < 0:
                    errs.append("%s:%d unterminated /* comment" % (label, line))
                    break
                line += text.count("\n", i, j)
                i = j + 2
                continue
        # strings and template literals
        if c in "\"'`":
            quote = c
            j = i + 1
            closed = False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    closed = True
                    break
                if text[j] == "\n" and quote != "`":
                    break  # unterminated single-line string
                j += 1
            if not closed:
                errs.append("%s:%d unterminated %s string" % (label, line, quote))
                break
            line += text.count("\n", i, j)
            i = j + 1
            continue
        if c in OPENERS:
            stack.append((c, line))
        elif c in PAIRS:
            if not stack:
                errs.append("%s:%d stray %s" % (label, line, c))
            elif stack[-1][0] != PAIRS[c]:
                errs.append("%s:%d %s closes %s opened on line %d"
                            % (label, line, c, stack[-1][0], stack[-1][1]))
                stack.pop()
            else:
                stack.pop()
        i += 1
    for ch, ln in stack:
        errs.append("%s:%d unclosed %s" % (label, ln, ch))
    return errs


def blank_raw(text):
    """Replace <script>/<style> bodies with blanks, keeping line numbers.

    Without this the HTML tag scanner reads a `<` inside a JavaScript
    string as the start of a tag, and a perfectly good file fails. The
    bodies are checked separately by inline_scripts.
    """
    low = text.lower()
    out = list(text)
    for tag in ("script", "style"):
        pos = 0
        while True:
            a = low.find("<" + tag, pos)
            if a < 0:
                break
            open_end = text.find(">", a)
            if open_end < 0:
                break
            b = low.find("</" + tag, open_end)
            if b < 0:
                break
            for k in range(open_end + 1, b):
                if out[k] != "\n":
                    out[k] = " "
            pos = b + 1
    return "".join(out)


def tags(text):
    """(name, is_close, is_selfclose, line) for every tag, crudely but safely."""
    out = []
    i, n, line = 0, len(text), 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c != "<":
            i += 1
            continue
        j = text.find(">", i)
        if j < 0:
            out.append(("(unterminated)", False, False, line))
            break
        body = text[i + 1:j]
        inner_lines = body.count("\n")
        if body.startswith("!--"):
            k = text.find("-->", i)
            if k < 0:
                out.append(("(unterminated comment)", False, False, line))
                break
            line += text.count("\n", i, k)
            i = k + 3
            continue
        is_close = body.startswith("/")
        is_self = body.rstrip().endswith("/")
        name = body.lstrip("/").split()[0].lower() if body.lstrip("/").split() else ""
        out.append((name, is_close, is_self, line))
        line += inner_lines
        i = j + 1
    return out


def html_balance(text, label):
    errs = []
    stack = []
    for name, is_close, is_self, line in tags(blank_raw(text)):
        if name.startswith("(") or name in VOID or is_self or not name:
            if name.startswith("("):
                errs.append("%s:%d %s tag" % (label, line, name))
            continue
        if is_close:
            if not stack:
                errs.append("%s:%d </%s> with nothing open" % (label, line, name))
            elif stack[-1][0] != name:
                errs.append("%s:%d </%s> but <%s> (line %d) is innermost"
                            % (label, line, name, stack[-1][0], stack[-1][1]))
                # recover: if it matches something further up, unwind to it
                names = [s[0] for s in stack]
                if name in names:
                    while stack and stack[-1][0] != name:
                        stack.pop()
                    if stack:
                        stack.pop()
            else:
                stack.pop()
        else:
            stack.append((name, line))
    for name, line in stack:
        errs.append("%s:%d <%s> never closed" % (label, line, name))
    return errs


def inline_scripts(text, label):
    """JS inside <script> blocks gets the bracket check too."""
    errs = []
    low = text.lower()
    pos = 0
    while True:
        a = low.find("<script", pos)
        if a < 0:
            break
        open_end = text.find(">", a)
        if open_end < 0:
            break
        b = low.find("</script", open_end)
        if b < 0:
            errs.append("%s: <script> never closed" % label)
            break
        errs += js_balance(text[open_end + 1:b], label + " <script>")
        pos = b + 1
    return errs


def main():
    if not WEB.is_dir():
        print("no web/ directory -- nothing to check")
        return 0
    errs, checked = [], 0
    for p in sorted(WEB.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(ROOT))
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix in (".html", ".htm"):
            errs += html_balance(text, rel)
            errs += inline_scripts(text, rel)
            checked += 1
        elif p.suffix == ".js":
            errs += js_balance(text, rel)
            checked += 1
        elif p.suffix == ".css":
            errs += js_balance(text, rel)
            checked += 1
    if checked == 0:
        print("web/ exists but holds no html/js/css -- nothing to check")
        return 1
    for e in errs:
        print("FAIL " + e)
    if errs:
        print("%d structural problem(s) across %d file(s)" % (len(errs), checked))
        return 1
    print("%d web file(s) structurally balanced" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
