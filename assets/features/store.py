"""Shared JSON store for feature modules.

Kept alongside app/db.py rather than replaced by it: a feature that needs
a flat list of dicts and no schema should not have to write a migration,
and a feature that needs relations should not be forced through JSON.
Which one a feature uses is a decision torch, not a law.
"""
import json
import pathlib

PATH = pathlib.Path(__file__).resolve().parent.parent / "data.json"


def load():
    if not PATH.exists():
        return []
    try:
        return json.loads(PATH.read_text() or "[]")
    except json.JSONDecodeError:
        return []


def save(rows):
    PATH.write_text(json.dumps(rows, indent=2))
