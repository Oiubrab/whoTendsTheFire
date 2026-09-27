#!/usr/bin/env python3
"""Does this project describe itself correctly?

Checks that pyproject.toml parses, that every package it claims to ship
actually exists, and that its console entry point resolves to a real
callable. All three are things that only fail at install time otherwise,
which is far too late.

    python3 tools/packagecheck.py
"""

import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import tomllib
except ImportError:  # 3.9/3.10
    tomllib = None


def main():
    p = ROOT / "pyproject.toml"
    if not p.exists():
        print("FAIL no pyproject.toml")
        return 1
    if tomllib is None:
        # no parser available; the most we can honestly assert is that the
        # required tables are present. Say so rather than claim a pass.
        text = p.read_text()
        missing = [k for k in ("[project]", "[build-system]") if k not in text]
        if missing:
            print("FAIL pyproject.toml missing %s" % ", ".join(missing))
            return 1
        print("ok   pyproject.toml has [project] and [build-system]")
        print("note tomllib unavailable on this interpreter; not fully parsed")
        return 0

    try:
        data = tomllib.load(p.open("rb"))
    except tomllib.TOMLDecodeError as e:
        print("FAIL pyproject.toml does not parse: %s" % e)
        return 1

    problems = 0
    proj = data.get("project")
    if not proj:
        print("FAIL pyproject.toml has no [project] table")
        return 1
    for field in ("name", "version"):
        if not proj.get(field):
            print("FAIL [project] is missing %s" % field)
            problems += 1
    if not problems:
        print("ok   %s %s" % (proj["name"], proj["version"]))

    readme = proj.get("readme")
    if readme and not (ROOT / readme).exists():
        print("FAIL readme %s declared but missing" % readme)
        problems += 1

    pkgs = data.get("tool", {}).get("setuptools", {}).get("packages", [])
    for pkg in pkgs:
        d = ROOT / pkg.replace(".", "/")
        if not (d / "__init__.py").exists():
            print("FAIL package %s declared but %s/__init__.py is missing" % (pkg, pkg))
            problems += 1
        else:
            print("ok   package %s" % pkg)

    for name, ref in (proj.get("scripts") or {}).items():
        if ":" not in ref:
            print("FAIL script %s: %r is not module:callable" % (name, ref))
            problems += 1
            continue
        mod_name, attr = ref.split(":", 1)
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print("FAIL script %s: cannot import %s (%s)" % (name, mod_name, e))
            problems += 1
            continue
        fn = getattr(mod, attr, None)
        if not callable(fn):
            print("FAIL script %s: %s has no callable %s" % (name, mod_name, attr))
            problems += 1
        else:
            print("ok   script %s -> %s" % (name, ref))

    deps = proj.get("dependencies") or []
    if deps:
        # the sandbox has no network, so a declared dependency cannot be
        # installed and cannot be honest about being satisfied
        print("FAIL dependencies declared (%s) but nothing can install them here"
              % ", ".join(deps))
        problems += 1
    else:
        print("ok   no third-party dependencies")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
