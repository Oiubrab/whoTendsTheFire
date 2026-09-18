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
import urllib.parse

REPO = os.path.dirname(os.path.abspath(__file__))
Q_SCRIPT = os.path.join(REPO, "q", "torches.q")
DB_DIR = os.path.join(REPO, "db")
RUNS_DIR = os.path.join(REPO, "runs")
UI_DIR = os.path.join(REPO, "ui")


def qstr(s: str) -> str:
    """A python string as a q string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def qsym(s: str) -> str:
    """A python string as a q symbol literal, safe for arbitrary characters."""
    return "`$" + qstr(s)


def run_q(expr: str):
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
        timeout=30,
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
                    "res: `nodes`edges!(0!select id,kind,rite,options from torches; 0!edges)"
                )
                self._send_json(result)
            elif parsed.path == "/api/state":
                qs = urllib.parse.parse_qs(parsed.query)
                pid = qs["pid"][0]
                result = run_q(f"res: state[{qsym(pid)}]")
                self._send_json(result)
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
                invocation = body.get("invocation", "")
                pid = "p" + secrets.token_hex(4)
                dest = os.path.join(RUNS_DIR, pid)
                os.makedirs(RUNS_DIR, exist_ok=True)
                expr = f"begin[{qsym(pid)};{qstr(invocation)};{qstr(dest)}]; res: state[{qsym(pid)}]"
                result = run_q(expr)
                self._send_json({"pid": pid, "state": result})
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
