#!/usr/bin/env python3
"""Command-line app. Features live as modules in features/ and are
discovered automatically -- this file does not change as they are added.

A feature module defines register(sub) adding exactly one subcommand,
and run(args) implementing it. A module that fails to import or fails to
register is skipped with a message on stderr: one bad generation must
not take down an app that eight good ones built.
"""
import argparse
import importlib
import pathlib
import pkgutil
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load_features(sub):
    fdir = HERE / "features"
    if not fdir.is_dir():
        return 0
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    n = 0
    for m in sorted(pkgutil.iter_modules([str(fdir)]), key=lambda x: x.name):
        if m.name.startswith("_") or m.name == "store":
            continue
        try:
            mod = importlib.import_module("features." + m.name)
        except Exception as e:
            print("skipping %s: %s" % (m.name, e), file=sys.stderr)
            continue
        if not hasattr(mod, "register"):
            continue
        try:
            mod.register(sub)
            n += 1
        except Exception as e:
            print("skipping %s: %s" % (m.name, e), file=sys.stderr)
    return n


def main():
    parser = argparse.ArgumentParser(
        description="usage: subcommands are provided by features/")
    sub = parser.add_subparsers(dest="command")
    load_features(sub)
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    # typed failures become a message and an exit code, not a traceback
    try:
        args.func(args)
    except Exception as e:
        try:
            from app import errors
        except ImportError:
            raise
        if not isinstance(e, errors.AppError):
            raise
        return errors.as_exit(e)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
