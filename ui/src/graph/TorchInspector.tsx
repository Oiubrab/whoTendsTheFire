import { useMemo, type ReactNode } from "react"
import type { CallLogEntry, GraphEdge, GraphNode, ProphecyState } from "../api/types"
import { KindBadge, StatusPill } from "../components/Badges"

type Stage = "working" | "ready" | "passed" | "failed" | "waiting"

interface Props {
  node: GraphNode
  edges: GraphEdge[] // this graph's edges only
  nodes: GraphNode[]
  state: ProphecyState
  calls: CallLogEntry[]
  runActive: boolean
  busy: boolean
  actions: ReactNode | null
}

// where a torch is in the current generation's walk. "working" means it is
// next in line AND something is driving the hearth right now; without a
// driver a frontier torch is merely "ready" (waiting on a human click).
function stageOf(id: string, state: ProphecyState, runActive: boolean, busy: boolean): { stage: Stage; option?: string } {
  const fired = [...state.trail].reverse().find((t) => t.torch === id)
  if (state.frontier.includes(id)) return { stage: busy || runActive ? "working" : "ready", option: fired?.option }
  if (fired) return { stage: fired.option === "fail" || fired.option === "failed" ? "failed" : "passed", option: fired.option }
  return { stage: "waiting" }
}

const STAGE_LABEL: Record<Stage, string> = {
  working: "in progress",
  ready: "ready to run",
  passed: "done",
  failed: "failed",
  waiting: "not reached yet",
}
const STAGE_PILL: Record<Stage, "live" | "warn" | "pass" | "fail" | "idle"> = {
  working: "live",
  ready: "warn",
  passed: "pass",
  failed: "fail",
  waiting: "idle",
}
const STAGE_BOX: Record<Stage, string> = {
  working: "border-ember text-ember2 bg-emberbg",
  ready: "border-warn text-warn bg-warnbg",
  passed: "border-pass text-pass bg-passbg",
  failed: "border-fail text-fail bg-failbg",
  waiting: "border-line2 text-dim bg-coal",
}

function fmtMs(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

// one box in the flowchart
function FlowBox({ id, stage, sub, big }: { id: string; stage: Stage; sub?: string; big?: boolean }) {
  return (
    <div
      className={`rounded-md border px-2.5 py-1.5 text-center font-mono ${STAGE_BOX[stage]} ${
        big ? "text-[12.5px] font-semibold ring-1 ring-current" : "text-[11.5px]"
      }`}
    >
      <div>{id}</div>
      {sub && <div className="text-[10px] font-normal opacity-80">{sub}</div>}
    </div>
  )
}

function Arrow({ label, taken, bad }: { label?: string; taken?: boolean; bad?: boolean }) {
  const tone = taken ? (bad ? "text-fail" : "text-ember2") : "text-dim"
  return (
    <div className={`flex flex-col items-center leading-none ${tone}`}>
      <div className={`h-3 w-px bg-current ${taken ? "" : "opacity-50"}`} />
      {label && <div className="my-0.5 font-mono text-[10px]">{label}</div>}
      <div className="text-[10px]">▼</div>
    </div>
  )
}

export function TorchInspector({
  node,
  edges,
  nodes,
  state,
  calls,
  runActive,
  busy,
  actions,
}: Props) {
  const { stage, option } = stageOf(node.id, state, runActive, busy)
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])
  const stageFor = (id: string) => stageOf(id, state, runActive, false)

  const incoming = edges.filter((e) => e.dst === node.id)
  const outgoing = edges.filter((e) => e.src === node.id)
  const isStart = incoming.length === 0

  // the edge actually taken out of this torch: the label it last fired with
  const fired = state.trail.filter((t) => t.torch === node.id)
  const taken = fired.length ? fired[fired.length - 1].option : undefined

  // predecessors that actually fired and led here
  const firedSrc = new Set(state.trail.map((t) => t.torch))

  const mine = useMemo(() => calls.filter((c) => c.torch === node.id).sort((a, b) => b.ts - a.ts), [calls, node.id])
  const failedOutput = state.lastcheck.torch === node.id && state.lastcheck.output ? state.lastcheck.output : ""
  const canAct = state.frontier.includes(node.id)

  return (
    <div className="grid gap-4">
      {/* header */}
      <div>
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-mono text-[15px] text-bone">{node.id}</h3>
          <KindBadge kind={node.kind} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusPill kind={STAGE_PILL[stage]} pulse={stage === "working"}>
            {STAGE_LABEL[stage]}
          </StatusPill>
          {option && stage !== "working" && (
            <span className="text-[12px] text-dim">
              last result <b className={stage === "failed" ? "text-fail" : "text-pass"}>{option}</b>
              {fired.length > 1 && ` · ran ${fired.length}×`}
            </span>
          )}
        </div>
      </div>

      {/* flowchart */}
      <div>
        <div className="mb-2 text-[11px] tracking-wide text-dim uppercase">Flow</div>
        <div className="grid justify-items-center gap-0 rounded-md border border-line bg-soot px-2 py-3">
          {isStart ? (
            <div className="text-[10.5px] text-dim">start of graph</div>
          ) : (
            <div className="flex w-full flex-wrap justify-center gap-1.5">
              {incoming.map((e, i) => {
                const s = stageFor(e.src).stage
                return <FlowBox key={i} id={e.src} stage={s === "working" ? "ready" : s} sub={`→ ${e.label}`} />
              })}
            </div>
          )}
          <Arrow taken={incoming.some((e) => firedSrc.has(e.src))} />
          <FlowBox id={node.id} stage={stage} sub={STAGE_LABEL[stage]} big />
          {outgoing.length > 0 && (
            <div className="mt-0 grid w-full gap-0">
              <div className="flex w-full flex-wrap items-start justify-center gap-3">
                {outgoing.map((e, i) => {
                  const isTaken = taken === e.label
                  const dst = e.dst ? byId.get(e.dst) : undefined
                  const ds = e.dst ? stageFor(e.dst).stage : "waiting"
                  return (
                    <div key={i} className="flex flex-col items-center">
                      <Arrow label={e.label} taken={isTaken} bad={e.label === "fail" || e.label === "failed"} />
                      {e.dst ? (
                        <FlowBox id={e.dst} stage={ds} sub={dst?.kind} />
                      ) : (
                        <div className="rounded-full border border-line2 px-2.5 py-0.5 font-mono text-[11px] text-dim">end</div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* what it is meant to do */}
      {node.rite && (
        <details className="group">
          <summary className="cursor-pointer text-[11px] tracking-wide text-dim uppercase select-none hover:text-ash">
            What this torch does
          </summary>
          <p className="mt-1.5 text-[12px] leading-relaxed whitespace-pre-wrap text-ash">{node.rite}</p>
        </details>
      )}

      {/* what happened */}
      {failedOutput && (
        <div>
          <div className="mb-1.5 text-[11px] tracking-wide text-dim uppercase">Last check output</div>
          <pre className="max-h-48 overflow-auto rounded-md border border-line bg-soot px-2.5 py-2 font-mono text-[11px] whitespace-pre-wrap text-[#f1b2a8]">
            {failedOutput}
          </pre>
        </div>
      )}

      {fired.length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] tracking-wide text-dim uppercase">Run history</div>
          <div className="grid gap-1">
            {fired.map((t) => (
              <div key={t.seq} className="flex justify-between rounded border border-line px-2 py-1 font-mono text-[11.5px]">
                <span className="text-dim">step {t.seq}</span>
                <span className={t.option === "fail" || t.option === "failed" ? "text-fail" : "text-pass"}>{t.option}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {mine.length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] tracking-wide text-dim uppercase">Model calls ({mine.length})</div>
          <div className="grid gap-1.5">
            {mine.slice(0, 4).map((c) => (
              <details key={c.ts} className="rounded border border-line">
                <summary className="flex cursor-pointer justify-between px-2 py-1 font-mono text-[11px] text-ash select-none">
                  <span>{new Date(c.ts).toLocaleTimeString()}</span>
                  <span className="text-dim">
                    {c.fake ? "fake" : fmtMs(c.durationMs)}
                    {c.replyTokens != null && ` · ${c.replyTokens} tok`}
                  </span>
                </summary>
                <pre className="max-h-40 overflow-auto border-t border-line px-2 py-1.5 font-mono text-[10.5px] whitespace-pre-wrap text-ash">
                  {c.reply || "(empty reply)"}
                </pre>
              </details>
            ))}
          </div>
        </div>
      )}

      {/* actions */}
      <div className={actions || !canAct ? "border-t border-line pt-3.5" : "hidden"}>
        {canAct ? (
          actions
        ) : (
          <p className="text-[11.5px] leading-snug text-dim">
            {stage === "waiting"
              ? "Not next in line — it becomes available once the torches before it have finished."
              : "Nothing to do here; this torch has already run in this generation."}
          </p>
        )}
      </div>
    </div>
  )
}
