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
