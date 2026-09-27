#!/usr/bin/env python3
"""HTTP dispatcher. Route modules live in api/ and are discovered.

Written once and never rewritten -- the same contract as cli.py. A route
module defines register(routes) and calls routes.add(METHOD, PATH, fn).
A module that fails to import or fails to register is skipped with a
message rather than taking the whole server down with it, because one
bad generation must not kill an app that eight good ones built.

    python3 serve.py --port 8080
"""

import argparse
import importlib
import json
import pathlib
import pkgutil
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
WEB = HERE / "web"


class Routes:
    """The routing table. Exact paths, plus one trailing wildcard form."""

    def __init__(self):
        self.exact = {}
        self.prefix = []

    def add(self, method, path, fn):
        method = method.upper()
        if path.endswith("*"):
            self.prefix.append((method, path[:-1], fn))
        else:
            self.exact[(method, path)] = fn

    def find(self, method, path):
        fn = self.exact.get((method, path))
        if fn:
            return fn, {}
        # /thing/1 matches a registered /thing/:id
        for (m, p), f in self.exact.items():
            if m != method:
                continue
            want, got = p.strip("/").split("/"), path.strip("/").split("/")
            if len(want) != len(got):
                continue
            params, ok = {}, True
            for w, g in zip(want, got):
                if w.startswith(":"):
                    params[w[1:]] = g
                elif w != g:
                    ok = False
                    break
            if ok:
                return f, params
        for m, pre, f in self.prefix:
            if m == method and path.startswith(pre):
                return f, {}
        return None, {}

    def paths(self):
        return sorted({p for _, p in self.exact} | {p + "*" for _, p, _ in self.prefix})


def load_routes():
    routes = Routes()
    adir = HERE / "api"
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    routes.add("GET", "/api/health", lambda req: {"ok": True, "routes": routes.paths()})
    # the browser cannot list a directory, so the shell asks for the view
    # manifest instead. This is what keeps index.html from being rewritten
    # every time a view is added.
    routes.add("GET", "/api/views", lambda req: {"views": [
        p.name for p in sorted((WEB / "views").glob("*.js"))]
        if (WEB / "views").is_dir() else []})
    if not adir.is_dir():
        return routes
    for m in sorted(pkgutil.iter_modules([str(adir)]), key=lambda x: x.name):
        if m.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module("api." + m.name)
        except Exception as e:
            print("skipping api/%s: %s" % (m.name, e), file=sys.stderr)
            continue
        if not hasattr(mod, "register"):
            continue
        try:
            mod.register(routes)
        except Exception as e:
            print("skipping api/%s: %s" % (m.name, e), file=sys.stderr)
    return routes


class Request:
    """What a handler receives. Deliberately tiny."""

    def __init__(self, method, path, query, params, body, headers):
        self.method = method
        self.path = path
        self.query = query
        self.params = params
        self.body = body
        self.headers = headers

    def json(self):
        if not self.body:
            return {}
        try:
            return json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    routes = None
    server_version = "app/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _write(self, status, payload, ctype="application/json"):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, default=str).encode()
            ctype = "application/json"
        elif isinstance(payload, str):
            payload = payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (WEB / rel).resolve()
        try:
            target.relative_to(WEB.resolve())
        except ValueError:
            self._write(403, {"error": "forbidden"})
            return
        if not target.is_file():
            self._write(404, {"error": "not found", "path": path})
            return
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._write(200, target.read_bytes(), ctype)

    def _serve(self, method):
        raw = self.path
        path, _, qs = raw.partition("?")
        query = {}
        for pair in qs.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                query[k] = v
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        fn, params = self.routes.find(method, path)
        if fn is None:
            if method == "GET" and WEB.is_dir() and not path.startswith("/api/"):
                self._static(path)
                return
            self._write(404, {"error": "no route", "method": method, "path": path})
            return
        req = Request(method, path, query, params, body, self.headers)
        try:
            result = fn(req)
        except Exception:
            tb = traceback.format_exc()
            print(tb, file=sys.stderr)
            self._write(500, {"error": "handler raised", "traceback": tb.splitlines()[-1]})
            return
        if isinstance(result, tuple) and len(result) == 2:
            self._write(result[0], result[1])
        elif result is None:
            self._write(204, b"", "application/json")
        else:
            self._write(200, result)

    def do_GET(self):
        self._serve("GET")

    def do_POST(self):
        self._serve("POST")

    def do_PUT(self):
        self._serve("PUT")

    def do_PATCH(self):
        self._serve("PATCH")

    def do_DELETE(self):
        self._serve("DELETE")


def main():
    ap = argparse.ArgumentParser(description="usage: run the HTTP API")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--list", action="store_true", help="print routes and exit")
    args = ap.parse_args()

    Handler.routes = load_routes()
    if args.list:
        for p in Handler.routes.paths():
            print(p)
        return
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("listening on http://%s:%d" % (args.host, args.port), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
