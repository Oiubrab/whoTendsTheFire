"""In-memory log of every model call, for the Activity tab's inspector.

Not persisted across a restart, unlike endreason/laststatus: those
describe the prophecy itself, a call log is forensic data about HOW an
answer was reached, and losing it on restart is an acceptable tradeoff
for not keeping full prompt/reply text in db/ forever. Shared by
server.py's own ask_model (the UI's step-mode/manual calls) and
agent.py's (the Phase 2 background runner's calls) -- both import this
directly rather than one reaching into the other's module state.
"""

import threading
import time

_LOG: dict[str, list[dict]] = {}
_LOCK = threading.Lock()
MAX_PER_PID = 300


def record(pid, torch, prompt, reply, duration_ms, prompt_tokens, reply_tokens, model, fake):
    if not pid:
        return
    entry = {
        "torch": torch,
        "prompt": prompt,
        "reply": reply or "",
        "durationMs": duration_ms,
        "promptTokens": prompt_tokens,
        "replyTokens": reply_tokens,
        "model": model,
        "fake": fake,
        "ts": time.time(),
    }
    with _LOCK:
        lst = _LOG.setdefault(pid, [])
        lst.append(entry)
        if len(lst) > MAX_PER_PID:
            del lst[: len(lst) - MAX_PER_PID]


def for_pid(pid):
    with _LOCK:
        return list(_LOG.get(pid, []))
