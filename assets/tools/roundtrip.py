#!/usr/bin/env python3
"""Write something through the API, then read it back and demand it.

This is the gate that catches the failure every other check misses: a
handler that validates its input, returns 201, and stores nothing. The
server starts, the route answers, nothing 500s, the smoke test passes,
the page renders -- and the application does not work.

The rule it enforces is stated in the authoring torch's contract, so it
is a check against a declared obligation rather than a guess: a POST
handler accepts a JSON body with a `name` field and persists it, and the
GET on the same path returns what was persisted.

A path with a POST but no matching GET is reported and skipped, not
failed: there is nothing to read back through.

    python3 tools/roundtrip.py
"""

import json
import re
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOT_TIMEOUT = 15.0
MARKER = "roundtrip-probe-%d" % int(time.time())


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


def call(port, method, path, body=None):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def pairs():
    """Paths carrying both a GET and a POST, from the source."""
    sys.path.insert(0, str(ROOT / "tools"))
    import survey
    by_path = {}
    for r in survey.routes():
        by_path.setdefault(r["path"], set()).add((r.get("method") or "GET").upper())
    both, writeonly = [], []
    for path, methods in sorted(by_path.items()):
        if "POST" not in methods:
            continue
        if "GET" in methods:
            both.append(path)
        else:
            writeonly.append(path)
    return both, writeonly


def main():
    if not (ROOT / "serve.py").exists():
        print("no serve.py -- nothing to round-trip")
        return 1
    both, writeonly = pairs()
    if not both and not writeonly:
        print("no POST routes -- nothing to round-trip")
        return 0

    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "serve.py", "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if not wait_up(port, proc):
            out = proc.stdout.read() if proc.poll() is not None else ""
            print("FAIL server did not start")
            if out:
                print(out[-1500:])
            return 1

        for path in writeonly:
            print("skip %s has POST but no GET -- nothing to read back through" % path)

        missing_re = re.compile(r"missing field\(s\):\s*(.+)", re.IGNORECASE)
        failures = 0
        for path in both:
            value = "%s-%s" % (MARKER, path.strip("/").replace("/", "-"))
            # a generated CRUD route's actual field names are not known
            # here, and guessing {"name", "value"} only ever matched a
            # route that happened to be called exactly that. Start with
            # that guess, but if the handler names what it actually wants
            # -- errors.Invalid says "missing field(s): a, b, c" -- retry
            # with the marker in every one of them, so this works for any
            # resource's field list rather than one fixed shape.
            body_json = {"name": value, "value": value}
            status, body = call(port, "POST", path, body_json)
            for _ in range(2):
                if status != 400:
                    break
                try:
                    detail = json.loads(body).get("detail", "")
                except (ValueError, TypeError):
                    detail = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
                m = missing_re.search(detail)
                if not m:
                    break
                added = False
                for f in (x.strip() for x in m.group(1).split(",")):
                    if f and f not in body_json:
                        body_json[f] = value
                        added = True
                if not added:
                    break
                status, body = call(port, "POST", path, body_json)
            if status == 0:
                print("FAIL POST %s -> no response (%s)" % (path, body[:120]))
                failures += 1
                continue
            if status >= 500:
                print("FAIL POST %s -> %d, handler raised\n     %s" % (path, status, body[:300]))
                failures += 1
                continue
            if status >= 400:
                print("FAIL POST %s -> %d, would not accept %r\n     %s"
                      % (path, status, body_json, body[:300]))
                failures += 1
                continue

            status, body = call(port, "GET", path)
            if status >= 400 or status == 0:
                print("FAIL GET %s -> %d after a successful POST\n     %s"
                      % (path, status, body[:300]))
                failures += 1
                continue
            if value not in body:
                print("FAIL %s accepted a POST and did not store it." % path)
                print("     wrote %r, and GET came back without it:" % value)
                print("     %s" % body[:300])
                failures += 1
                continue
            print("ok   %s round-trips: POST stored it, GET returned it" % path)

        checked = len(both)
        print("%d path(s) round-tripped, %d failure(s)" % (checked, failures))
        return 1 if failures else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
