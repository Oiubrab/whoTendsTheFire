"""Settings, with one rule: environment beats file beats default.

A new setting is one line added to DEFAULTS. Nothing else changes, and
nothing needs to know the setting exists to pass it through.
"""

import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
PREFIX = "APP_"

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8080,
    "log_level": "info",
    "page_size": 20,
}


def _coerce(default, raw):
    if isinstance(default, bool):
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default
    return raw


def load():
    settings = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            for k, v in json.loads(CONFIG_PATH.read_text() or "{}").items():
                if k in settings:
                    settings[k] = _coerce(DEFAULTS[k], v)
        except ValueError:
            pass
    for k in DEFAULTS:
        env = os.environ.get(PREFIX + k.upper())
        if env is not None:
            settings[k] = _coerce(DEFAULTS[k], env)
    return settings


def get(name, fallback=None):
    return load().get(name, fallback)
