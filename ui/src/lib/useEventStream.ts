import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import type { RunEvent } from "../api/types"
import { useRunStore, type RunMode } from "./runStore"

// Mounted once, in AppShell. Takes an initial snapshot from GET
// /api/runs (so a fresh page load -- or a reload mid-run -- shows the
// truth immediately, not just whatever happens after this connects) and
// then an EventSource keeps it live. Every event also invalidates the
// relevant React Query cache entries rather than trying to hand-patch
// cached state from the event's own (deliberately small) payload --
// the event says something changed and for which pid; refetching that
// pid's /api/state is simpler and cannot drift out of sync with it.
export function useEventStream() {
  const qc = useQueryClient()
  const upsert = useRunStore((s) => s.upsert)
  const remove = useRunStore((s) => s.remove)
  const setSnapshot = useRunStore((s) => s.setSnapshot)
  const setConnected = useRunStore((s) => s.setConnected)

  useEffect(() => {
    let cancelled = false

    api.runsList().then((rows) => {
      if (cancelled) return
      setSnapshot(
        rows.map((r) => ({
          hearth: r.hearth,
          pid: r.pid,
          mode: r.mode as RunMode,
          status: r.status,
          pendingApproval: r.pendingApproval
            ? { hearth: r.hearth, pid: r.pendingApproval.pid, invocation: r.pendingApproval.invocation, offerable: r.pendingApproval.offerable }
            : null,
        })),
      )
    })

    const invalidateRun = (hearth: string, pid?: string) => {
      qc.invalidateQueries({ queryKey: ["hearths"] })
      qc.invalidateQueries({ queryKey: ["lineage", hearth] })
      if (pid) {
        qc.invalidateQueries({ queryKey: ["state", pid] })
        qc.invalidateQueries({ queryKey: ["files", pid] })
        qc.invalidateQueries({ queryKey: ["calls", pid] })
      }
    }

    const es = new EventSource("/api/events")
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.onmessage = (ev) => {
      if (!ev.data) return
      let parsed: RunEvent
      try {
        parsed = JSON.parse(ev.data)
      } catch {
        return
      }
      switch (parsed.type) {
        case "approval_needed":
          upsert(parsed.hearth, {
            pid: parsed.pid,
            status: "waiting for approval",
            pendingApproval: { hearth: parsed.hearth, pid: parsed.pid, invocation: parsed.invocation, offerable: parsed.offerable },
          })
          break
        case "torch":
          upsert(parsed.hearth, { pid: parsed.pid, status: `${parsed.torch} → ${parsed.option}` })
          invalidateRun(parsed.hearth, parsed.pid)
          break
        case "generation_start":
          upsert(parsed.hearth, { pid: parsed.pid })
          break
        case "generation_end":
          invalidateRun(parsed.hearth, parsed.pid)
          break
        case "kindled":
          upsert(parsed.hearth, { pid: parsed.pid, status: `kindled generation ${parsed.generation}: ${parsed.graph}`, pendingApproval: null })
          invalidateRun(parsed.hearth, parsed.pid)
          break
        case "error":
          upsert(parsed.hearth, { status: `error: ${parsed.message}`, pendingApproval: null })
          invalidateRun(parsed.hearth)
          break
        case "runner_finished":
          remove(parsed.hearth)
          invalidateRun(parsed.hearth, parsed.pid)
          break
      }
    }

    return () => {
      cancelled = true
      es.close()
    }
  }, [qc, upsert, remove, setSnapshot, setConnected])
}
