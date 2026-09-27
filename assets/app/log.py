"""One logger, configured once, level from config.

Feature modules call log.get(__name__) and nothing else. Handler setup
happens exactly once no matter how many modules ask.
"""

import logging
import sys

_configured = False
LEVELS = {"debug": logging.DEBUG, "info": logging.INFO,
          "warning": logging.WARNING, "error": logging.ERROR}


def _setup():
    global _configured
    if _configured:
        return
    try:
        from app import config
        level = LEVELS.get(str(config.get("log_level", "info")).lower(), logging.INFO)
    except Exception:
        level = logging.INFO
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("app")
    root.handlers[:] = [h]
    root.setLevel(level)
    root.propagate = False
    _configured = True


def get(name="app"):
    _setup()
    short = name.split(".")[-1]
    return logging.getLogger("app." + short)
