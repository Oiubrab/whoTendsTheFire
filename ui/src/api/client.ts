import type {
  BeginResult,
  BlockedRow,
  ChooseResult,
  FileListing,
  GraphInfo,
  GraphPayload,
  Hearth,
  KindleResult,
  LightResult,
  LineageRow,
  ProphecyState,
  ProposeResult,
} from "./types"

export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const json = await res.json()
  if (json && typeof json === "object" && "error" in json) {
    throw new ApiError(String((json as { error: unknown }).error))
  }
  return json as T
}

const get = <T>(path: string) => request<T>("GET", path)
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body)

export const api = {
  graph: () => get<GraphPayload>("/api/graph"),
  graphs: () => get<GraphInfo[]>("/api/graphs"),
  hearths: () => get<Hearth[]>("/api/hearths"),
  lineage: (hearth: string) => get<LineageRow[]>(`/api/lineage?hearth=${encodeURIComponent(hearth)}`),
  state: (pid: string) => get<ProphecyState>(`/api/state?pid=${encodeURIComponent(pid)}`),
  file: (pid: string) => get<FileListing>(`/api/file?pid=${encodeURIComponent(pid)}`),
  blocked: (pid: string) => get<BlockedRow[]>(`/api/blocked?pid=${encodeURIComponent(pid)}`),
  quarantined: (pid: string) => get<{ files: Record<string, string> }>(`/api/quarantined?pid=${encodeURIComponent(pid)}`),
  gitlog: (pid: string) => get<{ commits: { hash: string; date: string; subject: string }[] }>(`/api/gitlog?pid=${encodeURIComponent(pid)}`),
  gitshow: (pid: string, hash: string) => get<{ diff: string }>(`/api/gitshow?pid=${encodeURIComponent(pid)}&hash=${encodeURIComponent(hash)}`),

  begin: (body: { invocation: string; graph?: string; evolution?: boolean; diskcap?: number; maxproph?: number; label?: string }) =>
    post<BeginResult>("/api/begin", body),
  light: (pid: string, torch: string, option: string) => post<LightResult>("/api/light", { pid, torch, option }),
  choose: (pid: string, torch: string) => post<ChooseResult>("/api/choose", { pid, torch }),
  propose: (pid: string, torch: string) => post<ProposeResult>("/api/propose", { pid, torch }),
  choosegraph: (pid: string, torch: string, invocation: string) =>
    post<ChooseResult>("/api/choosegraph", { pid, torch, invocation }),
  authorize: (pid: string, torch: string) => post<{ bytes: number; path: string }>("/api/authorize", { pid, torch }),
  kindle: (pid: string, invocation: string, graph: string, brownfield = true) =>
    post<KindleResult>("/api/kindle", { pid, invocation, graph, brownfield }),
  halt: (hearth: string) => post<{ halted: boolean }>("/api/halt", { hearth }),
  resume: (hearth: string) => post<{ halted: boolean }>("/api/resume", { hearth }),
  label: (hearth: string, label: string) => post<{ label: string }>("/api/label", { hearth, label }),

  runsList: () => get<import("./types").ServerRunStatus[]>("/api/runs"),
  runsStart: (hearth: string, pid: string, mode: string) =>
    post<{ started: boolean }>("/api/runs/start", { hearth, pid, mode }),
  runsStop: (hearth: string) => post<{ stopped: boolean }>("/api/runs/stop", { hearth }),
  runsApprove: (hearth: string, action: "accept" | "reject", graph?: string) =>
    post<{ ok: boolean }>("/api/runs/approve", { hearth, action, graph }),
}
