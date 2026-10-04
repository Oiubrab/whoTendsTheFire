"""Drives a lineage in a background thread, independent of any browser
tab or CLI invocation -- Phase 2 of the UI plan ("the engine moves to
the server").

Deliberately NOT a third implementation of the walk loop. agent.py's
run_prophecy() is already the tested one (used by the CLI); this module
imports it and supplies two hooks (approve_kindle, on_event) that let a
background thread pause for a human's approval and publish what it did,
without agent.py needing to know threads, queues or SSE exist.
"""

import queue
import threading

import agent

RUNNERS: dict[str, "LineageRunner"] = {}
RUNNERS_LOCK = threading.Lock()

SUBSCRIBERS: list[queue.Queue] = []
SUBSCRIBERS_LOCK = threading.Lock()


def broadcast(event: dict) -> None:
    with SUBSCRIBERS_LOCK:
        subs = list(SUBSCRIBERS)
    for q in subs:
        q.put(event)


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with SUBSCRIBERS_LOCK:
        SUBSCRIBERS.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with SUBSCRIBERS_LOCK:
        if q in SUBSCRIBERS:
            SUBSCRIBERS.remove(q)


class LineageRunner:
    def __init__(self, hearth: str, pid: str, mode: str, by_id: dict, ember: str, all_edges: list, graph: str):
        self.hearth = hearth
        self.pid = pid
        self.mode = mode  # "autonomous" | "approve"
        self.by_id = by_id
        self.ember = ember
        self.all_edges = all_edges
        self.graph = graph
        self.stop_event = threading.Event()
        self.approval_event = threading.Event()
        self.approval_result: tuple[bool, str | None] | None = None
        self.pending_approval: dict | None = None
        self.thread: threading.Thread | None = None
        self.status = "starting"

    def alive(self) -> bool:
        return bool(self.thread and self.thread.is_alive())


def start(hearth: str, pid: str, mode: str, bridge: str) -> LineageRunner:
    with RUNNERS_LOCK:
        existing = RUNNERS.get(hearth)
        if existing and existing.alive():
            raise RuntimeError(f"a runner is already active for hearth {hearth}")

    # agent.py's module-level BRIDGE is what every one of its http_json
    # calls targets -- this process IS the bridge, so pointing it at
    # ourselves is correct, not circular: the runner is just another
    # client of the same API the browser and the CLI already use.
    agent.BRIDGE = bridge
    graph_data = agent.http_json(f"{bridge}/api/graph")
    by_id = {n["id"]: n for n in graph_data["nodes"]}
    state = agent.http_json(f"{bridge}/api/state?pid={pid}")

    runner = LineageRunner(hearth, pid, mode, by_id, state["ember"], graph_data["edges"], state["graph"])
    with RUNNERS_LOCK:
        RUNNERS[hearth] = runner
    runner.thread = threading.Thread(target=_drive, args=(runner,), daemon=True)
    runner.thread.start()
    return runner


def stop(hearth: str) -> bool:
    with RUNNERS_LOCK:
        runner = RUNNERS.get(hearth)
    if not runner:
        return False
    runner.stop_event.set()
    runner.approval_event.set()  # unblock a thread parked in approve_kindle
    return True


def approve(hearth: str, action: str, graph: str | None) -> None:
    with RUNNERS_LOCK:
        runner = RUNNERS.get(hearth)
    if not runner or not runner.pending_approval:
        raise RuntimeError("no pending approval for this hearth")
    runner.approval_result = (action == "accept", graph)
    runner.pending_approval = None
    runner.approval_event.set()


def active_runs() -> list[dict]:
    with RUNNERS_LOCK:
        runners = list(RUNNERS.values())
    return [
        {
            "hearth": r.hearth,
            "pid": r.pid,
            "mode": r.mode,
            "status": r.status,
            "pendingApproval": r.pending_approval,
        }
        for r in runners
        if r.alive() or r.pending_approval
    ]


def _drive(runner: LineageRunner) -> None:
    hearth = runner.hearth
    agent.GRAPH_EDGES = [e for e in runner.all_edges if e["graph"] == runner.graph]

    def approve_kindle(invocation: str, offerable: list[str]):
        runner.pending_approval = {"pid": runner.pid, "invocation": invocation, "offerable": offerable}
        runner.status = "waiting for approval"
        broadcast({
            "type": "approval_needed", "hearth": hearth, "pid": runner.pid,
            "invocation": invocation, "offerable": offerable,
        })
        runner.approval_event.wait()
        runner.approval_event.clear()
        if runner.stop_event.is_set():
            return (False, None)
        result = runner.approval_result
        runner.approval_result = None
        return result or (False, None)

    def on_event(ev: dict):
        runner.status = f"{ev['torch']} → {ev['option']}"
        broadcast({"type": "torch", "hearth": hearth, "pid": runner.pid, **ev})

    try:
        while not runner.stop_event.is_set():
            broadcast({"type": "generation_start", "hearth": hearth, "pid": runner.pid})
            next_graph, next_invocation, reason = agent.run_prophecy(
                runner.pid, runner.by_id, runner.ember,
                approve_kindle=approve_kindle if runner.mode == "approve" else None,
                on_event=on_event,
                should_stop=runner.stop_event.is_set,
            )
            broadcast({"type": "generation_end", "hearth": hearth, "pid": runner.pid, "reason": reason})

            if runner.stop_event.is_set():
                runner.status = "stopped"
                break
            if not next_invocation:
                runner.status = f"finished: {reason}"
                break

            try:
                spawned = agent.http_json(f"{agent.BRIDGE}/api/kindle", {
                    "pid": runner.pid, "invocation": next_invocation, "graph": next_graph,
                })
            except Exception as e:  # noqa: BLE001 -- surfaced to the UI as an event, not a crash
                runner.status = f"kindle failed: {e}"
                broadcast({"type": "error", "hearth": hearth, "message": str(e)})
                break
            if "error" in spawned:
                runner.status = f"kindle failed: {spawned['error']}"
                broadcast({"type": "error", "hearth": hearth, "message": spawned["error"]})
                break

            runner.pid = spawned["pid"]
            agent.GRAPH_EDGES = [e for e in runner.all_edges if e["graph"] == next_graph]
            broadcast({
                "type": "kindled", "hearth": hearth, "pid": runner.pid,
                "generation": spawned["state"]["generation"], "graph": next_graph,
            })
    except Exception as e:  # noqa: BLE001 -- a background thread with no caller to propagate to
        runner.status = f"error: {e}"
        broadcast({"type": "error", "hearth": hearth, "message": str(e)})
    finally:
        broadcast({"type": "runner_finished", "hearth": hearth, "pid": runner.pid, "status": runner.status})
