import { useMemo, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { toast } from "sonner"
import type { HearthContext } from "./HearthLayout"
import { useCalls, useGraphLibrary, useInvalidateRun } from "../../api/hooks"
import { TorchGraph } from "../../graph/TorchGraph"
import { TorchInspector } from "../../graph/TorchInspector"
import { useRunStore } from "../../lib/runStore"
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

  const thisGraphEdges = useMemo(() => lib?.edges.filter((e) => e.graph === state.graph) ?? [], [lib, state.graph])
  const runActive = !!useRunStore((s) => s.runs[hearth.id])
  const { data: calls } = useCalls(pid, { poll: runActive })

  const lit = useMemo(() => new Set(state.trail.map((t) => t.torch)), [state.trail])
  const frontier = useMemo(() => new Set(state.frontier), [state.frontier])

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
            <TorchInspector
              node={selected}
              nodes={lib.nodes}
              edges={thisGraphEdges}
              state={state}
              calls={calls ?? []}
              runActive={runActive}
              busy={busy}
              actions={
                selected.kind === "authoring" ? null : (
                  <>
                    <TorchActions
                      node={selected}
                      busy={busy}
                      onLight={(opt) => run(() => api.light(pid, selected.id, opt))}
                      onKindle={() => setKindling(selected)}
                    />
                    <p className="mt-1.5 text-[11.5px] leading-snug text-dim">{HINTS[selected.kind]}</p>
                  </>
                )
              }
            />
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

const HINTS: Record<string, string> = {
  kindling: "Asks the model to propose the next generation's graph, which you then approve.",
  validation: "Runs this check against the project now; pass or fail decides which torch comes next.",
  action: "Pick an outcome to record it manually and move the walk on.",
  decision: "Pick an outcome to record it manually and move the walk on.",
}

function TorchActions({
  node,
  busy,
  onLight,
  onKindle,
}: {
  node: GraphNode
  busy: boolean
  onLight: (option: string) => void
  onKindle: () => void
}) {
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
