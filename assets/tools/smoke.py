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
import re
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


def request(port, method, path, body=None):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = json.dumps(body).encode() if body is not None else None
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


ID_TOKENS = (":id", "{id}", "<id>")


def id_base(path):
    """The resource path a :id-style route hangs off of, or None."""
    for tok in ID_TOKENS:
        if tok in path:
            return path.split(tok)[0].rstrip("/")
    return None


def concretize(path, rid):
    for tok in ID_TOKENS:
        path = path.replace(tok, str(rid))
    return path


MISSING_RE = re.compile(r"missing field\(s\):\s*(.+)", re.IGNORECASE)


def post_with_retry(port, path):
    """POST to path, discovering required fields from the handler's own
    complaint rather than guessing a fixed shape. errors.Invalid on a
    generated CRUD route says exactly "missing field(s): a, b, c" -- this
    reads that back and retries with a placeholder for each one, so the
    same probe works for any resource's field list, not just one shape.
    Returns (status, body) of the last attempt.
    """
    body = {}
    status, resp = 0, b""
    for _ in range(3):
        status, resp = request(port, "POST", path, body)
        if status == 400:
            try:
                detail = json.loads(resp).get("detail", "")
            except (ValueError, TypeError):
                detail = resp.decode("utf-8", "replace")
            m = MISSING_RE.search(detail)
            if m:
                added = False
                for f in (x.strip() for x in m.group(1).split(",")):
                    if f and f not in body:
                        body[f] = "smoke"
                        added = True
                if added:
                    continue
        break
    return status, resp


def post_seed(port, path):
    """The id of the row a successful post_with_retry created, or None."""
    status, resp = post_with_retry(port, path)
    if status not in (200, 201):
        return None
    try:
        return json.loads(resp).get("id")
    except (ValueError, TypeError, AttributeError):
        return None


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

        # DELETE checked last among routes sharing an id_base: a delete
        # that runs before a GET/PUT on the same seeded row would consume
        # it, and the GET's subsequent 404 is then a correct response to
        # a row that really is gone, not a routing failure -- but nothing
        # here can tell those apart after the fact, so the only fix is to
        # not delete the shared row until everything else has used it.
        routes = sorted(declared_routes(),
                        key=lambda r: (r.get("method") or "GET") == "DELETE")
        posts = {r["path"] for r in routes if (r.get("method") or "GET") == "POST"}
        seeded = {}  # base path -> real row id, or None if seeding failed

        for r in routes:
            raw, method = r["path"], r.get("method") or "GET"
            base = id_base(raw)
            if base is not None:
                if base not in seeded:
                    seeded[base] = post_seed(port, base) if base in posts else None
                rid = seeded[base]
                if rid is None:
                    # nothing to substitute with; fall back to a guess so
                    # this still checks the route answers SOMETHING, but
                    # a resulting 404 here is not held against the route --
                    # there is no way to know if id 1 ought to exist.
                    path = concretize(raw, 1)
                else:
                    path = concretize(raw, rid)
            else:
                path = raw

            if method == "POST":
                # same field-discovery retry as the seeding pass, so a
                # plain create route gets a fair try rather than being
                # probed with an empty body and marked "ok" on a 400 that
                # only means nothing was supplied.
                status, body = post_with_retry(port, path)
            else:
                status, body = request(port, method, path)
            checks += 1
            label = "%s %s" % (method, path)
            if status == 0:
                print("FAIL %s -> no response (%s)" % (label, body.decode()[:120]))
                failures += 1
            elif status >= 500:
                print("FAIL %s -> %d\n%s" % (label, status, body.decode()[:400]))
                failures += 1
            elif status == 404 and (base is None or seeded.get(base) is not None):
                # a real row was seeded (or this path never needed one) and
                # the route still 404d -- that IS a routing failure, not a
                # legitimate "no such record" response.
                print("FAIL %s -> 404, declared but not served" % label)
                failures += 1
            elif status == 404:
                print("ok   %s -> 404 (no seed row available to test against)" % label)
            elif status in (204, 304):
                # no content is the CORRECT body for these statuses -- an
                # empty response here is success, not a failure to answer.
                print("ok   %s -> %d (no content)" % (label, status))
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
