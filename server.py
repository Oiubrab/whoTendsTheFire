#!/usr/bin/env python3
"""Local bridge between the torches.q graph and the browser UI.

Runs entirely on stdlib -- no pip install needed. Each API call shells
out to q once, loading whatever's in db/ (or seeding it, first run),
running one expression, and persisting the result back to db/.
"""

import http.server
import json
import os
import secrets
import socketserver
import subprocess
import sys
import re
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
Q_SCRIPT = os.path.join(REPO, "q", "torches.q")
DB_DIR = os.path.join(REPO, "db")
RUNS_DIR = os.environ.get("RUNS_OVERRIDE") or os.path.join(REPO, "runs")
UI_DIR = os.path.join(REPO, "ui")


def qstr(s: str) -> str:
    """A python string as a q string literal.

    Newlines matter here: q reads this script line by line, so an
    unescaped newline inside a literal ends the statement mid-string and
    the rest of the file is parsed as code. Model-authored source is
    full of them. Anything else non-printable goes out as octal, which
    is the only general escape q accepts.
    """
    out = ['"']
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("\\%03o" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def qsym(s: str) -> str:
    """A python string as a q symbol literal, safe for arbitrary characters."""
    return "`$" + qstr(s)


def run_q(expr: str, timeout: int = 30):
    """Run q statements against the persisted graph; expr must end by setting `res`
    (e.g. "res: 1+1" or "foo[]; res: state[...]") -- `res::X; Y` are two separate
    top-level statements in q, not a sequence returning Y, so this can't be done
    by wrapping an arbitrary caller expression in `res: {expr}` after the fact."""
    boot = "loaddb[]" if os.path.exists(os.path.join(DB_DIR, "torches")) else "savedb[]"
    script = f"{boot};\n{expr};\n-1 .j.j res;\nsavedb[];\nexit 0\n"
    proc = subprocess.run(
        ["q", Q_SCRIPT, "-q"],
        input=script,
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=timeout,
    )
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError(f"q produced no output.\nstderr: {proc.stderr}\nscript:\n{script}")
    # a torch's own code can print to stdout too (via system/runin) before our
    # result line -- the JSON blob is always the last line, since .j.j never
    # emits a raw embedded newline.
    last_line = out.splitlines()[-1]
    try:
        return json.loads(last_line)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"q did not return valid JSON.\nstdout: {out}\nstderr: {proc.stderr}") from e


OLLAMA = "http://localhost:11434"
MODEL = "torch-gpt-oss"

# Nearly every bug in this system has been plumbing, not intelligence:
# quoting that ate shell variables, a .py extension appended to a shell
# target, an empty test suite that passed, a scaffold that clobbered the
# previous generation. None needed a real model to surface -- they needed
# the pipeline run once, end to end, with canned answers. FAKE_MODEL=1
# makes a full multi-generation run take seconds instead of forty
# minutes, which is the difference between catching those before they
# ship and finding them three layers downstream.
FAKE_MODEL = os.environ.get("FAKE_MODEL") == "1"

FAKE_FEATURE = '''from features import store


def register(sub):
    p = sub.add_parser("count", help="Count stored rows")
    p.set_defaults(func=run)


def run(args):
    rows = store.load()
    print("rows: %d" % len(rows))
'''

FAKE_DEMO = "python3 cli.py --help\n"

FAKE_TEST = '''#!/bin/sh
out=$(python3 cli.py count)
case "$out" in
  "rows: "*) ;;
  *) echo "unexpected: $out"; exit 1 ;;
esac
'''


FAKE_KINDLES = []


def fake_answer(prompt, target=None):
    import re as _re
    """Canned but REAL artifacts -- they must actually compile, run and
    pass, or the harness proves nothing about the pipeline.

    Keyed on the target path, not on prompt text: the brief embeds the
    current source, so every prompt contains "register(sub)" and matching
    on content returned Python for the .sh targets."""
    if target:
        if target.endswith(".py"):
            m = _re.search(r"gen(\d+)", target)
            name = "count%s" % (m.group(1) if m else "1")
            return FAKE_FEATURE.replace('"count"', '"%s"' % name)
        if target.startswith("tests/"):
            m = _re.search(r"gen(\d+)", target)
            name = "count%s" % (m.group(1) if m else "1")
            return FAKE_TEST.replace("cli.py count", "cli.py %s" % name)
        if target.endswith(".sh"):
            return FAKE_DEMO
    if "next thing to build" in prompt or "next subcommand" in prompt or "next capability" in prompt:
        FAKE_KINDLES.append(1)
        # let the harness reach three generations, then stop cleanly
        return ("DECLINE" if len(FAKE_KINDLES) >= 3
                else "Add a subcommand that reports the newest row.")
    return "done"
FINAL = "<|channel|>final<|message|>"


def _extract(raw):
    """gpt-oss reasons in an `analysis` channel before answering in `final`.
    A generation cut short by the token budget never reaches `final`, and
    the leftover reasoning must not be mistaken for an answer."""
    if FINAL in raw:
        text = raw.rsplit(FINAL, 1)[1]
        for stop in ("<|end|>", "<|return|>", "<|start|>"):
            text = text.split(stop)[0]
        return text.strip() or None
    if "<|channel|>" in raw or "<|message|>" in raw:
        return None
    return raw.strip() or None


def parses_as_python(code):
    try:
        compile(code, "<authored>", "exec")
        return True
    except SyntaxError:
        return False


def syntax_ok(target, code):
    """Refuse to write a file that doesn't parse, whatever its language.

    Only .py was checked before, so a shell script truncated by the token
    budget was written anyway -- it then failed the suite with 'unexpected
    end of file', which repair could not distinguish from a wrong
    assertion."""
    if target.endswith(".py"):
        return parses_as_python(code)
    if target.endswith(".sh"):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write(code)
            tmp = fh.name
        try:
            return subprocess.run(["sh", "-n", tmp],
                                  capture_output=True, timeout=20).returncode == 0
        finally:
            os.unlink(tmp)
    return True


def ask_model(prompt, num_predict=6000, effort=None, target=None):
    if FAKE_MODEL:
        return fake_answer(prompt, target)
    """effort="low" cuts gpt-oss's analysis-channel reasoning, which is
    ~30% of wall clock on mechanical tasks (measured: 120s -> 84s) and
    buys nothing when the job is 'write four shell commands'."""
    body = {
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.3, "num_predict": num_predict},
    }
    if effort:
        body["system"] = f"Reasoning: {effort}"
    payload = json.dumps(body).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return _extract(json.loads(r.read()).get("response", ""))


def strip_fence(text):
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            body = parts[1]
            if "\n" in body:
                first, rest = body.split("\n", 1)
                if first.strip().lower() in ("python", "python3", "py", ""):
                    return rest
            return body
    return text


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path in ("/", "/index.html"):
                self._send_file(os.path.join(UI_DIR, "index.html"), "text/html; charset=utf-8")
            elif parsed.path == "/api/graph":
                result = run_q(
                    "nd: 0!select id,kind,rite,options from torches;"
                    "mem: select graphs: distinct graph by torch from members where lib=`main;"
                    "nd: update graph: {$[count x; first x; `]} each mem[([]torch:nd`id)]`graphs from nd;"
                    "res: `nodes`edges!(nd; 0!select from edges where lib=`main)"
                )
                self._send_json(result)
            elif parsed.path == "/api/graphs":
                self._send_json(run_q("res: 0!graphs"))
            elif parsed.path == "/api/lineage":
                qs = urllib.parse.parse_qs(parsed.query)
                hid = qs["hearth"][0]
                self._send_json(run_q(f"res: lineage[{qsym(hid)}]"))
            elif parsed.path == "/api/state":
                qs = urllib.parse.parse_qs(parsed.query)
                pid = qs["pid"][0]
                result = run_q(f"res: state[{qsym(pid)}]")
                self._send_json(result)
            elif parsed.path == "/api/file":
                qs = urllib.parse.parse_qs(parsed.query)
                pid = qs["pid"][0]
                dest = run_q(f"res: exec first dest from prophecies where id={qsym(pid)}")
                out = {}
                for root, _, names in os.walk(dest):
                    if "__pycache__" in root:
                        continue
                    for n in names:
                        if n.startswith(".") or n.endswith(".pyc"):
                            continue
                        fp = os.path.join(root, n)
                        rel = os.path.relpath(fp, dest)
                        try:
                            with open(fp) as f:
                                out[rel] = f.read()
                        except (OSError, UnicodeDecodeError):
                            out[rel] = "(unreadable)"
                self._send_json({"dest": dest, "files": out})
            elif parsed.path == "/api/brieftext":
                qs = urllib.parse.parse_qs(parsed.query)
                pid, torch = qs["pid"][0], qs["torch"][0]
                result = run_q(f"res: briefText[{qsym(pid)};{qsym(torch)}]")
                self._send_json({"text": result})
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            body = self._read_json_body()
            if parsed.path == "/api/begin":
                # lights a hearth: the founding invocation becomes the ember,
                # and the first prophecy is its first cell.
                invocation = body.get("invocation", "")
                graph = body.get("graph", "g.pycli")
                evolution = bool(body.get("evolution", False))
                hid = "h" + secrets.token_hex(4)
                pid = "p" + secrets.token_hex(4)
                # the id stays random because it is a database key, but the
                # DIRECTORY gets a date and a slug: twenty folders named
                # h2bde009c tell a human nothing about when they ran or what
                # they were building, and reconstructing that later needed
                # archaeology across nine db snapshots.
                slug = re.sub(r"[^a-z0-9]+", "-", invocation.lower()).strip("-")[:40] or "run"
                stamp = time.strftime("%Y-%m-%d-%H%M")
                dest = os.path.join(RUNS_DIR, f"{stamp}-{slug}-{hid[1:5]}", pid)
                os.makedirs(RUNS_DIR, exist_ok=True)
                expr = (
                    f"ignite[{qsym(hid)};{qstr(invocation)};{'1b' if evolution else '0b'}];"
                    f"begin[{qsym(hid)};{qsym(pid)};{qsym(graph)};{qstr(invocation)};{qstr(dest)}];"
                    f"res: state[{qsym(pid)}]"
                )
                result = run_q(expr)
                self._send_json({"hearth": hid, "pid": pid, "state": result})
            elif parsed.path == "/api/choose":
                # the model picks an option at a decision torch, so the UI
                # can run itself instead of waiting on a human click.
                pid, tid = body["pid"], body["torch"]
                brief = run_q(f"res: briefText[{qsym(pid)};{qsym(tid)}]")
                t = run_q(f"res: `kind`rite`options!("
                          f"torches[{qsym(tid)}]`kind;"
                          f"torches[{qsym(tid)}]`rite;"
                          f"torches[{qsym(tid)}]`options)")
                opts = t["options"]
                if len(opts) == 1:
                    self._send_json({"option": opts[0], "asked": False})
                else:
                    prompt = (f"{brief}\n\nYou are at torch '{tid}'.\n"
                              + (f"Its question: {t['rite']}\n" if t["rite"] else "")
                              + "Choose exactly one of these and reply with ONLY that text:\n"
                              + ", ".join(opts) + "\n\nOption:")
                    reply = ask_model(prompt, num_predict=600) or ""
                    pick = next((o for o in opts if o.lower() in reply.lower()), opts[0])
                    self._send_json({"option": pick, "asked": True, "said": reply[:200]})
            elif parsed.path == "/api/propose":
                # the model proposes the daughter's invocation
                pid, tid = body["pid"], body["torch"]
                brief = run_q(f"res: briefText[{qsym(pid)};{qsym(tid)}]")
                st = run_q(f"res: state[{qsym(pid)}]")
                rite = run_q(f"res: torches[{qsym(tid)}]`rite")
                prompt = (f"{brief}\n\nTHE EMBER (what this lineage serves):\n  {st['ember']}\n\n"
                          f"{rite}\n\n"
                          "Reply with ONE sentence naming the single next thing to build, nothing else.\n"
                          "If nothing worthwhile remains, reply exactly: DECLINE\n\nNext:")
                reply = ask_model(prompt, num_predict=800)
                if not reply:
                    self._send_json({"decline": True})
                else:
                    line = next((l.strip() for l in reply.splitlines() if l.strip()), "")
                    if not line or line.upper().startswith("DECLINE") or "<|" in line or len(line) < 10:
                        self._send_json({"decline": True})
                    else:
                        self._send_json({"invocation": line.strip('"').strip()})
            elif parsed.path == "/api/authorize":
                # The torch declares its target. A target ending in "/" means
                # "a new module in this directory" -- each generation writes
                # its own small file rather than re-emitting the whole app,
                # which is what keeps cost per generation flat.
                pid, tid = body["pid"], body["torch"]
                brief = run_q(f"res: briefText[{qsym(pid)};{qsym(tid)}]")
                t = run_q(f"res: `rite`target!(torches[{qsym(tid)}]`rite; torches[{qsym(tid)}]`target)")
                st = run_q(f"res: state[{qsym(pid)}]")
                target = t["target"] or "cli.py"
                if "{n}" in target:
                    # the target carries its own extension -- appending .py to
                    # every directory target named a shell test tests/gen1.py,
                    # which was then correctly refused for not compiling, so
                    # no test was ever written and the suite passed on an
                    # empty glob.
                    if tid.startswith("repair"):
                        d = os.path.join(st["dest"], os.path.dirname(target))
                        mods = sorted(
                            (f for f in os.listdir(d) if f.endswith(".py")
                             and not f.startswith("_") and f != "store.py"),
                            key=lambda f: os.path.getmtime(os.path.join(d, f)),
                        ) if os.path.isdir(d) else []
                        target = (os.path.join(os.path.dirname(target), mods[-1])
                                  if mods else target.replace("{n}", "1"))
                    else:
                        target = target.replace("{n}", str(st["generation"]))
                prompt = (
                    f"{brief}\n\n{t['rite']}\n\n"
                    f"Reply with the complete contents of {target} and nothing else. "
                    "No explanation, no markdown fences.\n"
                )
                effort = "low" if target.endswith(".sh") else None
                code = None
                for budget in (4000, 9000):
                    reply = ask_model(prompt, num_predict=budget, effort=effort, target=target)
                    if not reply:
                        continue
                    cand = strip_fence(reply).strip() + "\n"
                    if syntax_ok(target, cand):
                        code = cand
                        break
                if code is None:
                    self._send_json({"error": f"model output for {target} did not parse, even with a larger budget"})
                else:
                    n = run_q(f"res: author[{qsym(pid)};{qstr(target)};{qstr(code)}]")
                    self._send_json({"bytes": n, "path": target})
            elif parsed.path == "/api/author":
                # the model wrote a file; the engine decides where it lands
                pid, path, content = body["pid"], body["path"], body["content"]
                expr = f"res: author[{qsym(pid)};{qstr(path)};{qstr(content)}]"
                self._send_json({"bytes": run_q(expr)})
            elif parsed.path == "/api/quarantine":
                # A model-authored test can simply be wrong. After repair has
                # had its go, set the test aside rather than let a bad
                # assertion bounce against a working feature until the step
                # ceiling kills the lineage.
                pid = body["pid"]
                st = run_q(f"res: state[{qsym(pid)}]")
                tdir = os.path.join(st["dest"], "tests")
                qdir = os.path.join(tdir, "quarantine")
                os.makedirs(qdir, exist_ok=True)
                moved = []
                for f in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
                    if not f.endswith(".sh"):
                        continue
                    src = os.path.join(tdir, f)
                    ok = run_q(f"res: first sandboxed[{qstr(st['dest'])};"
                               f"{qstr('sh tests/' + f)}]", timeout=120)
                    if not ok:
                        os.rename(src, os.path.join(qdir, f))
                        moved.append(f)
                self._send_json({"quarantined": moved})
            elif parsed.path == "/api/evolve":
                # race model-proposed graph variants in sandboxes, keep the winner
                pid = body["pid"]
                muts = body["mutations"]
                scratch = os.path.join(RUNS_DIR, "_race")
                os.makedirs(scratch, exist_ok=True)
                # The model reliably invents edge labels that don't exist
                # ("select", "generate script"), so most proposals used to
                # burn a full sandboxed race only to score -1000. Check them
                # against the real graph first and drop the impossible ones
                # before spending any propellant on them.
                p_ = run_q(f"res: `hearth`graph!(prophecies[{qsym(pid)}]`hearth; prophecies[{qsym(pid)}]`graph)")
                lb = run_q(f"res: hearths[{qsym(p_['hearth'])}]`lib")
                real = run_q(f"res: 0!select src,label,dst from edges where lib={qsym(lb)}, graph={qsym(p_['graph'])}")
                known_t = set(run_q("res: exec id from torches"))
                pairs = {(e["src"], e["label"]) for e in real}
                def valid(m):
                    op = m.get("op")
                    if op == "insert":
                        return (m.get("torch") in known_t
                                and (m.get("after"), m.get("label")) in pairs)
                    if op == "rewire":
                        return ((m.get("src"), m.get("label")) in pairs
                                and (m.get("dst") in known_t or m.get("dst") in ("", None)))
                    if op == "drop":
                        return any(m.get("torch") in (e["src"], e["dst"]) for e in real)
                    return False
                dropped = [m for m in muts if not valid(m)]
                muts = [m for m in muts if valid(m)]
                if not muts:
                    self._send_json({"error": f"no valid mutations proposed ({len(dropped)} rejected)"})
                    return

                def qmut(m):
                    # `$"..." rather than a bare backtick symbol: the model
                    # writes these values, so they may contain anything.
                    keys = "".join(f"`{k}" for k in m)
                    vals = ";".join(qsym(str(v)) if str(v) else "`" for v in m.values())
                    return f"(({keys})!({vals}))"
                # a single dict in parens is just that dict in q, not a
                # one-element list -- race would iterate its keys instead.
                mlist = (f"enlist {qmut(muts[0])}" if len(muts) == 1
                         else "(" + ";".join(qmut(m) for m in muts) + ")")
                expr = (
                    f"p: prophecies[{qsym(pid)}];"
                    f"res: @[{{race . x}}; (p`hearth; p`graph; {mlist}; {qstr(scratch)}); "
                    f"{{(enlist `error)!enlist x}}]"
                )
                self._send_json(run_q(expr, timeout=600))
            elif parsed.path == "/api/kindle":
                # reproduction. dest is the caller's choice: the parent's own
                # dest extends the codebase in place, a fresh one builds
                # alongside it.
                pid = body["pid"]
                invocation = body["invocation"]
                graph = body.get("graph", "g.pycli")
                brownfield = bool(body.get("brownfield", True))
                newpid = "p" + secrets.token_hex(4)
                expr_dest = (
                    f"(exec first dest from prophecies where id={qsym(pid)})"
                    if brownfield
                    else None
                )
                if expr_dest is None:
                    hid = run_q(f"res: exec first hearth from prophecies where id={qsym(pid)}")
                    newdest = qstr(os.path.join(RUNS_DIR, str(hid), newpid))
                else:
                    newdest = expr_dest
                expr = (
                    f"r: @[{{kindle . x}}; ({qsym(pid)};{qsym(newpid)};{qsym(graph)};"
                    f"{qstr(invocation)};{newdest}); {{(enlist `error)!enlist x}}];"
                    f"res: `result`state!(r; state[{qsym(newpid)}])"
                )
                result = run_q(expr)
                if isinstance(result.get("result"), dict) and "error" in result["result"]:
                    self._send_json({"error": result["result"]["error"]})
                else:
                    self._send_json({"pid": newpid, "state": result["state"]})
            elif parsed.path == "/api/light":
                pid, torch, option = body["pid"], body["torch"], body["option"]
                expr = (
                    f"r: @[{{lightin . x}}; ({qsym(pid)};{qsym(torch)};{qsym(option)}); "
                    f"{{(enlist `error)!enlist x}}]; res: `result`state!(r; state[{qsym(pid)}])"
                )
                result = run_q(expr)
                self._send_json(result)
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8420
    os.makedirs(RUNS_DIR, exist_ok=True)
    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"whoTendsTheFire UI: http://127.0.0.1:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
