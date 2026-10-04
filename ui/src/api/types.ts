// Shapes returned by server.py. Field names match the JSON exactly --
// see server.py's run_q()/._send_json() call sites, not a schema file;
// the bridge has no OpenAPI spec, this file is the closest thing to one.

export type TorchKind = "decision" | "action" | "validation" | "kindling" | "authoring"

export interface GraphNode {
  id: string
  kind: TorchKind
  rite: string
  options: string[]
  graph: string | null
}

export interface GraphEdge {
  lib: string
  graph: string
  src: string
  label: string
  dst: string | null
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphInfo {
  lib: string
  id: string
  root: string
  purpose: string
}

export interface Hearth {
  id: string
  ember: string
  evolution: boolean
  lib: string
  diskcap: number
  maxproph: number
  halt: string
  born: string
  generations: number
  halted: boolean
  diskused: number
  label: string
}

export interface LineageRow {
  id: string
  parent: string | null
  generation: number
  graph: string
  invocation: string
  dest: string
}

export interface TrailRow {
  seq: number
  torch: string
  option: string
}

export interface LastCheck {
  torch: string | null
  option: string | null
  output: string
}

export interface CallLogEntry {
  torch: string | null
  prompt: string
  reply: string
  durationMs: number
  promptTokens: number | null
  replyTokens: number | null
  model: string
  fake: boolean
  ts: number
}

export interface ProphecyState {
  invocation: string
  ember: string
  dest: string
  graph: string
  hearth: string
  parent: string | null
  generation: number
  frontier: string[]
  trail: TrailRow[]
  capabilities: string[]
  offerable: string[]
  tree: string[]
  lastcheck: LastCheck
  halted: boolean
  // lowercase -- matches q's own symbol name verbatim through .j.j,
  // unlike every other field here which happens to already be lowercase
  // for the same reason. Empty string, never null, when nothing has
  // ended yet (see getendreason[] in q/torches.q).
  endreason: string
}

export interface BlockedRow {
  graph: string
  missing: string[]
}

export interface FileListing {
  dest: string
  files: Record<string, string>
}

export interface GitCommit {
  hash: string
  date: string
  subject: string
}

export interface ChooseResult {
  option: string
  asked: boolean
  said?: string
}

export interface ProposeResult {
  invocation?: string
  decline?: boolean
}

export interface LightResult {
  result: {
    torch: string
    option: string
    tools: unknown[]
    filesWritten: number
    codeOk: boolean
    output: string[]
    next: string[]
  }
  state: ProphecyState
}

export interface BeginResult {
  hearth: string
  pid: string
  state: ProphecyState
}

export interface KindleResult {
  pid: string
  state: ProphecyState
}

// Shapes the Phase 2 server-side runner (runner.py) sends, over both
// GET /api/runs (a snapshot) and GET /api/events (as they happen). Named
// "Server*" to keep them visibly distinct from lib/runStore's LiveRun,
// which is the normalized, hearth-keyed shape the UI actually reads --
// pendingApproval here has no `hearth` field since it's already nested
// under one in the snapshot; the event stream repeats it at the top
// level instead since an event isn't nested under anything.
export interface ServerPendingApproval {
  pid: string
  invocation: string
  offerable: string[]
}

export interface ServerRunStatus {
  hearth: string
  pid: string
  mode: string
  status: string
  pendingApproval: ServerPendingApproval | null
}

export type RunEvent =
  | { type: "approval_needed"; hearth: string; pid: string; invocation: string; offerable: string[] }
  | { type: "torch"; hearth: string; pid: string; torch: string; kind: string; option: string; filesWritten: number }
  | { type: "generation_start"; hearth: string; pid: string }
  | { type: "generation_end"; hearth: string; pid: string; reason: string }
  | { type: "kindled"; hearth: string; pid: string; generation: number; graph: string }
  | { type: "error"; hearth: string; message: string }
  | { type: "runner_finished"; hearth: string; pid: string; status: string }
