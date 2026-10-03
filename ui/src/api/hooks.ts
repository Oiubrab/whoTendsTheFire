import { useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

// Hearth list is polled rather than pushed -- there is no event stream
// yet (that is Phase 2's server-side runner). A short interval keeps the
// dashboard and hearths screens feeling live without hammering the bridge,
// which shells out a real q process per request.
const LIST_POLL_MS = 4000
const STATE_POLL_MS = 3000

export function useHearths() {
  return useQuery({ queryKey: ["hearths"], queryFn: api.hearths, refetchInterval: LIST_POLL_MS })
}

export function useGraphLibrary() {
  return useQuery({ queryKey: ["graph"], queryFn: api.graph, staleTime: Infinity })
}

export function useGraphs() {
  return useQuery({ queryKey: ["graphs"], queryFn: api.graphs, staleTime: Infinity })
}

export function useLineage(hearth: string | undefined) {
  return useQuery({
    queryKey: ["lineage", hearth],
    queryFn: () => api.lineage(hearth!),
    enabled: !!hearth,
    refetchInterval: LIST_POLL_MS,
  })
}

export function useProphecyState(pid: string | undefined, opts?: { poll?: boolean }) {
  return useQuery({
    queryKey: ["state", pid],
    queryFn: () => api.state(pid!),
    enabled: !!pid,
    refetchInterval: opts?.poll ? STATE_POLL_MS : false,
  })
}

export function useFiles(pid: string | undefined) {
  return useQuery({ queryKey: ["files", pid], queryFn: () => api.file(pid!), enabled: !!pid })
}

export function useBlocked(pid: string | undefined, enabled: boolean) {
  return useQuery({ queryKey: ["blocked", pid], queryFn: () => api.blocked(pid!), enabled: enabled && !!pid })
}

export function useGitLog(pid: string | undefined) {
  return useQuery({ queryKey: ["gitlog", pid], queryFn: () => api.gitlog(pid!), enabled: !!pid })
}

export function useQuarantined(pid: string | undefined) {
  return useQuery({ queryKey: ["quarantined", pid], queryFn: () => api.quarantined(pid!), enabled: !!pid })
}

// a bundle of invalidations every mutation that changes run state needs,
// so each call site doesn't have to remember the whole list
export function useInvalidateRun() {
  const qc = useQueryClient()
  return (pid?: string, hearth?: string) => {
    if (pid) {
      qc.invalidateQueries({ queryKey: ["state", pid] })
      qc.invalidateQueries({ queryKey: ["files", pid] })
    }
    if (hearth) {
      qc.invalidateQueries({ queryKey: ["lineage", hearth] })
    }
    qc.invalidateQueries({ queryKey: ["hearths"] })
  }
}
