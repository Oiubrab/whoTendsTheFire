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
# overridable so an isolated test bridge cannot silently write into the
# real repo's db/ -- RUNS_OVERRIDE already isolated where a test
# prophecy's FILES went, but every test bridge run this session still
# shared the real db/ regardless, quietly accumulating test hearths in
# it. q's own savedb/loaddb read this same variable (as DB_OVERRIDE,
# inherited automatically since subprocess.run here passes no explicit
# env=), so setting it once here is enough for both sides to agree.
DB_DIR = os.environ.get("DB_OVERRIDE") or os.path.join(REPO, "db")
os.makedirs(DB_DIR, exist_ok=True)
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
    # db/torches was the check here before savedb/loaddb were split -- the
    # library no longer persists at all (it is always loaded fresh from
    # q/library.q), so that file is never written anymore and this check
    # was permanently false. Every call thought no state existed yet and
    # started blank, which meant nothing survived from one call to the
    # next: begin[] in one request, then state[] in the very next request,
    # found an empty hearths table. db/hearths is what runtime state now
    # writes, so it is what this has to check instead.
    boot = "loaddb[]" if os.path.exists(os.path.join(DB_DIR, "hearths")) else "savedb[]"
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
NUM_CTX = int(os.environ.get("NUM_CTX", "32768"))

# Deliberately free of any storage import. Which store exists is a
# decision the lineage makes at choose.storage, and a canned feature that
# assumed one of them turned a storage choice into a test failure.
FAKE_FEATURE = '''"""Count the rows in the CSV fixture."""
import csv
import pathlib


def register(sub):
    p = sub.add_parser("count", help="Count rows in sample.csv")
    p.set_defaults(func=run)


def run(args):
    path = pathlib.Path(__file__).resolve().parent.parent / "sample.csv"
    rows = list(csv.DictReader(path.open())) if path.exists() else []
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


FAKE_ROUTE = """from app import db, errors


def register(routes):
    routes.add("GET", "/api/thing%(n)s", list_things)
    routes.add("POST", "/api/thing%(n)s", make_thing)


def list_things(req):
    try:
        return {"things": db.query("select * from thing order by id limit 50")}
    except Exception:
        return {"things": []}


def make_thing(req):
    name = (req.json().get("name") or "").strip()
    if not name:
        raise errors.Invalid("name is required")
    return 201, {"name": name}
"""

FAKE_VIEW = """App.view("Thing%(n)s", function (main) {
  main.appendChild(App.el("p", { text: "things from the api" }));
  return App.api("/api/thing%(n)s").then(function (d) {
    main.appendChild(App.table(d.things || []));
    App.status("loaded");
  });
});
"""

FAKE_MIGRATION = """create table thing%(n)s (
  id integer primary key autoincrement,
  name text not null,
  created_at text default current_timestamp
);
"""

FAKE_APITEST = """#!/bin/sh
python3 serve.py --port 8071 >/dev/null 2>&1 &
SRV=$!
i=0
while [ $i -lt 40 ]; do
  python3 -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',8071))==0 else 1)" && break
  i=$((i+1))
  sleep 0.2
done
out=$(python3 -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8071/api/health'))['ok'])")
kill $SRV
[ "$out" = "True" ] || { echo "health check failed: $out"; exit 1; }
"""

FAKE_KINDLES = []

# One spec per generation, so a canned multi-generation run through
# g.resource exercises a distinct table each time rather than colliding
# with itself on the second pass.
FAKE_RESOURCE_SPECS = ["widget: label:text, qty:integer, done:boolean",
                       "invoice: item:text, amount:real"]
FAKE_RESOURCE_CALLS = []


def fake_answer(prompt, target=None, torch=None):
    import re as _re
    """Canned but REAL artifacts -- they must actually compile, run and
    pass, or the harness proves nothing about the pipeline.

    Keyed on the target path or the torch id, never on prompt text: the
    brief embeds the current source and the chronicle, so prompt-sniffing
    has broken twice already -- once when "register(sub)" appeared in
    every prompt and matched the wrong branch, once when the chronicle's
    own "choose.surface -> both" line satisfied a later torch's check
    meant for a different question entirely."""
    if target:
        m = _re.search(r"(\d+)", os.path.basename(target))
        n = m.group(1) if m else "1"
        # most specific first: tests/ before .sh, api/ before .py
        if target.startswith("tests/api"):
            return FAKE_APITEST
        if target.startswith("tests/"):
            return FAKE_TEST.replace("cli.py count", "cli.py count%s" % n)
        if target.startswith("api/"):
            return FAKE_ROUTE % {"n": n}
        if target.startswith("web/views/"):
            return FAKE_VIEW % {"n": n}
        if target.endswith(".sql"):
            return FAKE_MIGRATION % {"n": n}
        if target.endswith(".py"):
            return FAKE_FEATURE.replace('"count"', '"count%s"' % n)
        if target.endswith(".sh"):
            return FAKE_DEMO
        if target == ".resource-spec.txt":
            i = min(len(FAKE_RESOURCE_CALLS), len(FAKE_RESOURCE_SPECS) - 1)
            FAKE_RESOURCE_CALLS.append(1)
            return FAKE_RESOURCE_SPECS[i]
    # kindle.next and choose.graph are two separate calls now, not one --
    # the first writes the sentence and advances FAKE_KINDLES, the second
    # reads the SAME position back to answer consistently with it. Cycling
    # the graphs is deliberate -- a harness that only ever exercises one
    # arrangement proves nothing about the other seven.
    order = ["g.feature", "g.resource", "g.harden", "g.document"]
    if torch == "kindle.next":
        i = len(FAKE_KINDLES)
        FAKE_KINDLES.append(1)
        if i >= len(order):
            return "DECLINE"
        return "Add a subcommand that reports the newest row."
    if torch == "choose.graph":
        i = len(FAKE_KINDLES) - 1
        if 0 <= i < len(order):
            want = order[i]
            if want in prompt:
                return want
        return ""
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
    if target.endswith(".sql"):
        # sqlite is the thing that will run it, so sqlite is what judges it.
        # Parsed against a throwaway in-memory database, never the real one.
        import sqlite3
        try:
            con = sqlite3.connect(":memory:")
            con.executescript(code)
            con.close()
            return True
        except sqlite3.Error:
            return False
    if target.endswith(".js"):
        # no Node in the sandbox, so this is a bracket/string balance check
        # and is described as exactly that, not as a parse. It catches the
        # truncation and unclosed-brace failures that actually happen.
        return _brackets_balanced(code)
    return True


def _brackets_balanced(code):
    """Balance of (), [], {} outside strings and comments."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        if c == "/" and i + 1 < n and code[i + 1] == "/":
            j = code.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and code[i + 1] == "*":
            j = code.find("*/", i + 2)
            if j < 0:
                return False
            i = j + 2
            continue
        if c in "\"'`":
            j, closed = i + 1, False
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == c:
                    closed = True
                    break
                if code[j] == "\n" and c != "`":
                    break
                j += 1
            if not closed:
                return False
            i = j + 1
            continue
        if c in "([{":
            stack.append(c)
        elif c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
        i += 1
    return not stack


# Scaffold files are written by the engine and must never be picked as a
# repair target: a repair asked to fix "the module you just wrote" that
# lands on store.py or __init__.py destroys shared machinery.
NEVER_REPAIR = {"__init__.py", "store.py", "cli.py", "serve.py",
                "app.js", "app.css", "index.html"}


def resolve_target(target, tid, st):
    """Turn an authoring torch's declared target into a concrete path.

    `{n}`  -> the generation number, so each generation writes its own file
    `{nn}` -> the same, zero padded, for anything ordered by filename
              (migrations are applied in name order, and 10_x.sql sorting
              before 2_x.sql silently applies them in the wrong order)

    A repair torch has to land on the file that just failed rather than a
    new one, so it resolves to the most recently modified file in the same
    directory with the same extension. Matching on extension is what makes
    this work for a route, a view or a migration and not only a module.
    """
    if "{n}" not in target and "{nn}" not in target:
        return target
    gen = int(st.get("generation") or 1)
    ext = os.path.splitext(target)[1]
    if tid.startswith("repair"):
        d = os.path.join(st["dest"], os.path.dirname(target))
        if os.path.isdir(d):
            cands = [f for f in os.listdir(d)
                     if f.endswith(ext) and not f.startswith("_")
                     and f not in NEVER_REPAIR and not f.startswith(".")]
            if cands:
                newest = max(cands, key=lambda f: os.path.getmtime(os.path.join(d, f)))
                return os.path.join(os.path.dirname(target), newest)
        gen = 1
    return target.replace("{nn}", "%03d" % gen).replace("{n}", str(gen))


def ask_model(prompt, num_predict=6000, effort=None, target=None, torch=None):
    if FAKE_MODEL:
        return fake_answer(prompt, target, torch)
    """effort="low" cuts gpt-oss's analysis-channel reasoning, which is
    ~30% of wall clock on mechanical tasks (measured: 120s -> 84s) and
    buys nothing when the job is 'write four shell commands'."""
    body = {
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": num_predict,
            # without this Ollama uses 4096 and truncates the prompt from
            # the front, silently discarding the invocation and the ember
            "num_ctx": NUM_CTX,
        },
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
                # g.pycli was the founding graph of the old 12-torch library
                # and no longer exists at all -- a UI "begin" click with no
                # explicit graph (the normal case) silently asked to walk a
                # graph that is not in the seed, got an empty frontier back,
                # and the prophecy ended after zero steps with no error.
                graph = body.get("graph", "g.found")
                evolution = bool(body.get("evolution", False))
                hid = "h" + secrets.token_hex(4)
                pid = "p" + secrets.token_hex(4)
                # the id stays random because it is a database key, but the
                # DIRECTORY gets a date and a slug: twenty folders named
                # h2bde009c tell a human nothing about when they ran or what
                # they were building, and reconstructing that later needed
                # archaeology across nine db snapshots.
                # A human has to be able to find this six days later. The name
                # carries when it ran and what it was for; the four hex digits
                # only break ties between two runs of the same ember in the
                # same minute.
                slug = re.sub(r"[^a-z0-9]+", "-", invocation.lower()).strip("-")[:40] or "run"
                stamp = time.strftime("%Y-%m-%d-%H%M")
                # "app", not the prophecy id: daughters extend the parent's
                # directory by default, so there is exactly one of these per
                # hearth and a hex name on it was pure noise.
                dest = os.path.join(RUNS_DIR, f"{stamp}-{slug}-{hid[1:5]}", "app")
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
                    reply = ask_model(prompt, num_predict=600, torch=tid) or ""
                    pick = next((o for o in opts if o.lower() in reply.lower()), opts[0])
                    self._send_json({"option": pick, "asked": True, "said": reply[:200]})
            elif parsed.path == "/api/propose":
                # kindle.next writes ONLY the invocation now -- what to
                # build, not how. It used to also pick the graph in the
                # same reply; split after watching a real lineage get the
                # sentence right five times running while getting the
                # graph wrong five times running, in the SAME response.
                # Asking for a closed-menu choice and an open invention in
                # one breath is exactly what docs/01's law/choice/invention
                # split exists to prevent. /api/choosegraph (below) does
                # the choosing now, informed by the sentence this writes,
                # once it already exists rather than alongside it.
                pid, tid = body["pid"], body["torch"]
                brief = run_q(f"res: briefText[{qsym(pid)};{qsym(tid)}]")
                st = run_q(f"res: state[{qsym(pid)}]")
                rite = run_q(f"res: torches[{qsym(tid)}]`rite")
                prompt = (
                    f"{brief}\n\nTHE EMBER (what this lineage serves):\n  {st['ember']}\n\n"
                    f"{rite}\n"
                )
                reply = ask_model(prompt, num_predict=400, torch=tid)
                if not reply:
                    self._send_json({"decline": True})
                else:
                    line = next((l.strip() for l in reply.splitlines() if l.strip()), "")
                    invocation = line.strip('"').strip() if line and not line.upper().startswith("DECLINE") else None
                    if not invocation or "<|" in invocation or len(invocation) < 10:
                        self._send_json({"decline": True})
                    else:
                        self._send_json({"invocation": invocation})
            elif parsed.path == "/api/choosegraph":
                # the second half of kindling: which arrangement fits the
                # invocation /api/propose already wrote. A plain decision
                # -- the menu is choose.graph's own options, the library's
                # graph ids -- just with that invocation prepended to the
                # prompt, since it does not exist in the brief itself
                # (rites are static; the sentence this answers was written
                # by the PREVIOUS torch, one step after the brief for this
                # call was already built from the chronicle).
                pid, tid = body["pid"], body["torch"]
                invocation = body["invocation"]
                brief = run_q(f"res: briefText[{qsym(pid)};{qsym(tid)}]")
                st = run_q(f"res: state[{qsym(pid)}]")
                t = run_q(f"res: `rite`options!(torches[{qsym(tid)}]`rite; torches[{qsym(tid)}]`options)")
                options = list(t["options"])
                offerable = set(st.get("offerable") or [])
                if offerable:
                    kept = [o for o in options if o in offerable]
                    if kept:
                        options = kept
                prompt = (
                    f"{brief}\n\nThe next generation will build this:\n\n  {invocation}\n\n"
                    f"{t['rite']}\n\n"
                    "Reply with ONLY one of these exact option names, nothing else:\n"
                    + ", ".join(options) + "\n\nOption:"
                )
                reply = ask_model(prompt, num_predict=200, torch=tid) or ""
                pick = next((o for o in sorted(options, key=len, reverse=True) if o in reply), options[0])
                self._send_json({"option": pick, "asked": True, "said": reply[:200]})
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
                target = resolve_target(target, tid, st)
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
                    # --fresh-dirs: build alongside rather than in place. This
                    # used to name the directory from the raw hearth id, which
                    # put generation 2 in runs/h9a3f21c8/ while generation 1 was
                    # in runs/2026-09-27-1251-slug-9a3f/ -- one lineage split
                    # across two unrelated-looking directories.
                    parent = run_q(f"res: exec first dest from prophecies where id={qsym(pid)}")
                    gen = run_q(f"res: 1 + exec first generation from prophecies where id={qsym(pid)}")
                    hearth_dir = os.path.dirname(str(parent))
                    newdest = qstr(os.path.join(hearth_dir, "gen%d" % int(gen)))
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
