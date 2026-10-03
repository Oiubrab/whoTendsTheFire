import { useMemo, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { toast } from "sonner"
import type { HearthContext } from "./HearthLayout"
import { useGraphLibrary, useInvalidateRun } from "../../api/hooks"
import { TorchGraph } from "../../graph/TorchGraph"
import { KindBadge } from "../../components/Badges"
import { api } from "../../api/client"
import type { GraphNode } from "../../api/types"
import { ManualKindleDialog } from "../../components/ManualKindleDialog"

export default function Graph() {
  const { hearth, pid, state } = useOutletContext<HearthContext>()
  const { data: lib } = useGraphLibrary()
  const [scope, setScope] = useState<"this" | "library">("this")
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const [kindling, setKindling] = useState<GraphNode | null>(null)
  const invalidate = useInvalidateRun()
  const [busy, setBusy] = useState(false)

  const nodes = useMemo(() => {
    if (!lib) return []
    if (scope === "library") return lib.nodes
    const inGraph = new Set(lib.edges.filter((e) => e.graph === state.graph).flatMap((e) => [e.src, e.dst].filter(Boolean) as string[]))
    return lib.nodes.filter((n) => inGraph.has(n.id))
  }, [lib, scope, state.graph])

  const edges = useMemo(() => {
    if (!lib) return []
    return scope === "library" ? lib.edges : lib.edges.filter((e) => e.graph === state.graph)
  }, [lib, scope, state.graph])

  const lit = useMemo(() => new Set(state.trail.map((t) => t.torch)), [state.trail])
  const frontier = useMemo(() => new Set(state.frontier), [state.frontier])
  const isFrontier = !!selected && frontier.has(selected.id)
  const lastTrail = selected ? [...state.trail].reverse().find((t) => t.torch === selected.id) : undefined
  const outcomes = selected ? edges.filter((e) => e.src === selected.id) : []

  if (!lib) return <div className="p-7 text-[13px] text-dim">Loading graph…</div>

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      invalidate(pid, hearth.id)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex items-center gap-2 rounded-md border border-line2 bg-char px-2.5 py-1 text-[12px]">
            Graph <b className="font-mono text-ember2">{state.graph}</b>
            <span className="text-dim">{nodes.length} torches</span>
          </span>
          <div className="inline-flex overflow-hidden rounded-md border border-line2">
            <button
              onClick={() => setScope("this")}
              className={`px-2.5 py-1 text-[12px] ${scope === "this" ? "bg-coal text-bone" : "text-ash hover:text-bone"}`}
            >
              This graph
            </button>
            <button
              onClick={() => setScope("library")}
              className={`px-2.5 py-1 text-[12px] ${scope === "library" ? "bg-coal text-bone" : "text-ash hover:text-bone"}`}
            >
              Whole library
            </button>
          </div>
        </div>
        <div className="text-[12px] text-dim">generation {state.generation}</div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[1fr_300px]">
        <div className="border-r border-line">
          <TorchGraph
            nodes={nodes}
            edges={edges}
            lit={lit}
            frontier={frontier}
            selectedId={selected?.id}
            onSelect={setSelected}
          />
        </div>
        <div className="overflow-y-auto bg-char p-4">
          {!selected ? (
            <div className="text-[13px] text-dim">Click a torch to inspect it.</div>
          ) : (
            <div className="grid gap-3.5">
              <div className="flex items-center justify-between">
                <h3 className="font-mono text-[15px] text-bone">{selected.id}</h3>
                <KindBadge kind={selected.kind} />
              </div>
              {selected.rite && <p className="text-[12.5px] text-ash">{selected.rite}</p>}

              {lastTrail && (
                <div className="text-[12px]">
                  <span className="text-dim">last result </span>
                  <span className={lastTrail.option === "fail" ? "text-fail" : "text-pass"}>{lastTrail.option}</span>
                </div>
              )}
              {selected.id === state.lastcheck.torch && state.lastcheck.output && (
                <pre className="max-h-40 overflow-auto rounded-md border border-line bg-soot px-2.5 py-2 font-mono text-[11px] whitespace-pre-wrap text-[#f1b2a8]">
                  {state.lastcheck.output}
                </pre>
              )}

              {outcomes.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[11px] tracking-wide text-dim uppercase">Outcomes</div>
                  <div className="grid gap-1">
                    {outcomes.map((e, i) => (
                      <div
                        key={i}
                        className="flex justify-between rounded border border-line px-2 py-1 font-mono text-[11.5px]"
                      >
                        <span className={e.label === "fail" ? "text-fail" : "text-ash"}>{e.label}</span>
                        <span className="text-dim">→ {e.dst || "end"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {isFrontier && (
                <div className="border-t border-line pt-3.5">
                  <div className="mb-2 text-[11px] tracking-wide text-dim uppercase">Available now</div>
                  <TorchActions
                    node={selected}
                    busy={busy}
                    onLight={(opt) => run(() => api.light(pid, selected.id, opt))}
                    onAuthor={() =>
                      run(async () => {
                        const r = await api.authorize(pid, selected.id)
                        toast.success(`wrote ${r.path} (${r.bytes} bytes)`)
                        await api.light(pid, selected.id, selected.options[0])
                      })
                    }
                    onKindle={() => setKindling(selected)}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {kindling && (
        <ManualKindleDialog
          pid={pid}
          hearth={hearth.id}
          node={kindling}
          offerable={state.offerable}
          onClose={() => setKindling(null)}
        />
      )}
    </div>
  )
}

function TorchActions({
  node,
  busy,
  onLight,
  onAuthor,
  onKindle,
}: {
  node: GraphNode
  busy: boolean
  onLight: (option: string) => void
  onAuthor: () => void
  onKindle: () => void
}) {
  if (node.kind === "authoring") {
    return (
      <button
        onClick={onAuthor}
        disabled={busy}
        className="w-full rounded-md bg-ember px-3 py-1.5 text-[12.5px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
      >
        Write with the model
      </button>
    )
  }
  if (node.kind === "kindling") {
    return (
      <button
        onClick={onKindle}
        disabled={busy}
        className="w-full rounded-md bg-ember px-3 py-1.5 text-[12.5px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
      >
        Propose the next generation
      </button>
    )
  }
  if (node.kind === "validation") {
    return (
      <button
        onClick={() => onLight(node.options[0])}
        disabled={busy}
        className="w-full rounded-md bg-ember px-3 py-1.5 text-[12.5px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
      >
        Run the check
      </button>
    )
  }
  return (
    <div className="grid gap-1.5">
      {node.options.map((opt) => (
        <button
          key={opt}
          onClick={() => onLight(opt)}
          disabled={busy}
          className="rounded-md border border-line2 px-3 py-1.5 text-left text-[12.5px] text-bone hover:border-ember disabled:opacity-50"
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
