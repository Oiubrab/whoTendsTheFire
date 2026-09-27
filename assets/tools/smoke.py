#!/usr/bin/env python3
"""Start the server, hit every route it declares, shut it down.

This is the backend's validation gate, and it is a real one: the server
is actually launched as a subprocess, actually connected to over a
socket, and every route found in api/ is actually requested. A route
that raises, 404s, or returns an empty body fails here. No model is
involved in deciding the outcome -- it is whatever the sockets said.

Uses a port chosen by the kernel rather than a fixed one, so two of
these racing in separate sandboxes cannot collide.

    python3 tools/smoke.py
"""

import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOT_TIMEOUT = 15.0


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_up(port, proc):
    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def declared_routes():
    sys.path.insert(0, str(ROOT / "tools"))
    import survey
    rows = survey.routes()
    seen, out = set(), []
    for r in rows:
        key = (r.get("method", "GET"), r["path"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def sample_body(path):
    """A minimal plausible JSON body for a write route."""
    return json.dumps({"name": "smoke", "value": 1}).encode()


def request(port, method, path):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = None
    if method in ("POST", "PUT", "PATCH"):
        data = sample_body(path)
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e).encode()


def concretize(path):
    for a in (":id", "{id}", "<id>"):
        path = path.replace(a, "1")
    return path


def main():
    if not (ROOT / "serve.py").exists():
        print("no serve.py -- nothing to smoke")
        return 1
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "serve.py", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if not wait_up(port, proc):
            out = ""
            if proc.poll() is not None:
                out = proc.stdout.read() or ""
            print("FAIL server did not come up on port %d" % port)
            if out:
                print(out[-2000:])
            return 1
        print("server up on port %d" % port)

        failures = 0
        checks = 0

        status, body = request(port, "GET", "/api/health")
        checks += 1
        if status != 200:
            print("FAIL GET /api/health -> %s" % status)
            failures += 1
        else:
            print("ok   GET /api/health -> 200 (%d bytes)" % len(body))

        for r in declared_routes():
            path = concretize(r["path"])
            method = r.get("method") or "GET"
            status, body = request(port, method, path)
            checks += 1
            label = "%s %s" % (method, path)
            if status == 0:
                print("FAIL %s -> no response (%s)" % (label, body.decode()[:120]))
                failures += 1
            elif status >= 500:
                print("FAIL %s -> %d\n%s" % (label, status, body.decode()[:400]))
                failures += 1
            elif status == 404:
                print("FAIL %s -> 404, declared but not served" % label)
                failures += 1
            elif not body:
                print("FAIL %s -> %d with empty body" % (label, status))
                failures += 1
            else:
                print("ok   %s -> %d (%d bytes)" % (label, status, len(body)))

        print("%d check(s), %d failure(s)" % (checks, failures))
        return 1 if failures else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
