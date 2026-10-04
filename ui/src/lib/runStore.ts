import { create } from "zustand"

export type RunMode = "autonomous" | "approve" | "step"

export interface PendingApproval {
  hearth: string
  pid: string
  invocation: string
  offerable: string[]
}

export interface LiveRun {
  hearth: string
  pid: string
  mode: RunMode
  status: string
  pendingApproval: PendingApproval | null
}

// Phase 2: the engine lives on the server now (runner.py), so this store
// no longer drives anything -- it's a pure reflection of what /api/events
// (and the GET /api/runs snapshot taken on connect) says is happening,
// shared by every tab. Multiple hearths can genuinely be running at once,
// which the old single {pid, hearth, running} shape from Phase 1 had no
// room for. Keyed by hearth id, since a hearth has at most one live
// runner at a time (server.py's runner.start() refuses a second).
interface RunState {
  runs: Record<string, LiveRun>
  connected: boolean
  setConnected: (c: boolean) => void
  upsert: (hearth: string, patch: Partial<LiveRun>) => void
  remove: (hearth: string) => void
  setSnapshot: (runs: LiveRun[]) => void
}

export const useRunStore = create<RunState>((set) => ({
  runs: {},
  connected: false,
  setConnected: (connected) => set({ connected }),
  upsert: (hearth, patch) =>
    set((s) => {
      const base: LiveRun = s.runs[hearth] ?? { hearth, pid: "", mode: "autonomous", status: "", pendingApproval: null }
      return { runs: { ...s.runs, [hearth]: { ...base, ...patch } } }
    }),
  remove: (hearth) =>
    set((s) => {
      const runs = { ...s.runs }
      delete runs[hearth]
      return { runs }
    }),
  setSnapshot: (runs) => set({ runs: Object.fromEntries(runs.map((r) => [r.hearth, r])) }),
}))

// the one pending approval to show, if any -- first-come, first-served
// when more than one hearth happens to be waiting at once. A queue/stack
// of approval dialogs is more than this needs right now.
export function firstPendingApproval(runs: Record<string, LiveRun>): PendingApproval | null {
  for (const r of Object.values(runs)) {
    if (r.pendingApproval) return r.pendingApproval
  }
  return null
}
