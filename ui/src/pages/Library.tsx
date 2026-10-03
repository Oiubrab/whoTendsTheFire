import { useMemo, useState } from "react"
import { useGraphLibrary, useGraphs } from "../api/hooks"
import { KindBadge } from "../components/Badges"
import { TorchGraph } from "../graph/TorchGraph"
import type { TorchKind } from "../api/types"

const KIND_ORDER: TorchKind[] = ["decision", "action", "validation", "authoring", "kindling"]
const KIND_COLOR: Record<TorchKind, string> = {
  decision: "var(--color-k-decision)",
  action: "var(--color-k-action)",
  validation: "var(--color-k-validation)",
  kindling: "var(--color-k-kindling)",
  authoring: "var(--color-k-authoring)",
}

export default function Library() {
  const { data: lib } = useGraphLibrary()
  const { data: graphs } = useGraphs()
  const [openGraph, setOpenGraph] = useState<string | null>(null)
  const [q, setQ] = useState("")

  const nodesByGraph = useMemo(() => {
    if (!lib) return {}
    const map: Record<string, Set<string>> = {}
    lib.edges.forEach((e) => {
      ;(map[e.graph] ??= new Set()).add(e.src)
      if (e.dst) map[e.graph].add(e.dst)
    })
    return map
  }, [lib])

  const filteredTorches = useMemo(() => {
    if (!lib) return []
    const needle = q.trim().toLowerCase()
    if (!needle) return lib.nodes
    return lib.nodes.filter((n) => n.id.toLowerCase().includes(needle) || n.rite.toLowerCase().includes(needle))
  }, [lib, q])

  if (!lib || !graphs) return <div className="p-7 text-[13px] text-dim">Loading…</div>

  const scoped = openGraph
    ? {
        nodes: lib.nodes.filter((n) => nodesByGraph[openGraph]?.has(n.id)),
        edges: lib.edges.filter((e) => e.graph === openGraph),
      }
    : null

  return (
    <div className="mx-auto max-w-6xl px-6 py-7">
      <div className="flex items-baseline justify-between">
        <h1 className="font-display text-[22px] font-[650]">Library</h1>
        <div className="text-[12.5px] text-dim">
          {graphs.length} graphs · {lib.nodes.length} torches · {lib.edges.length} edges
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        {graphs.map((g) => {
          const ids = nodesByGraph[g.id] ?? new Set()
          const kinds = lib.nodes.filter((n) => ids.has(n.id))
          const total = kinds.length || 1
          return (
            <button
              key={g.id}
              onClick={() => setOpenGraph(g.id)}
              className="rounded-lg border border-line bg-char p-3.5 text-left hover:border-line2"
            >
              <div className="flex items-baseline justify-between">
                <b className="font-mono text-[13px] text-ember2">{g.id}</b>
                <span className="text-[11.5px] text-dim">{kinds.length} torches</span>
              </div>
              <p className="mt-1.5 text-[12px] text-ash">{g.purpose}</p>
              <div className="mt-2.5 flex h-1.5 gap-px overflow-hidden rounded-full">
                {KIND_ORDER.map((k) => {
                  const n = kinds.filter((t) => t.kind === k).length
                  if (!n) return null
                  return <div key={k} style={{ width: `${(n / total) * 100}%`, background: KIND_COLOR[k] }} />
                })}
              </div>
            </button>
          )
        })}
      </div>

      {scoped && (
        <div className="mt-5 overflow-hidden rounded-xl border border-line bg-char">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="font-mono text-[13px] text-ember2">{openGraph}</h2>
            <button onClick={() => setOpenGraph(null)} className="text-[12px] text-ash hover:text-bone">
              close
            </button>
          </div>
          <div className="h-[420px]">
            <TorchGraph nodes={scoped.nodes} edges={scoped.edges} lit={new Set()} frontier={new Set()} />
          </div>
        </div>
      )}

      <div className="mt-5 rounded-xl border border-line bg-char">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Torches</h2>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="search…"
            className="rounded-md border border-line2 bg-soot px-2.5 py-1 text-[12px] text-bone outline-none placeholder:text-dim"
          />
        </div>
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="text-[11px] tracking-wide text-dim uppercase">
              <th className="px-4 py-2 text-left font-medium">Torch</th>
              <th className="px-4 py-2 text-left font-medium">Kind</th>
              <th className="px-4 py-2 text-left font-medium">Outcomes</th>
              <th className="px-4 py-2 text-left font-medium">Rite</th>
            </tr>
          </thead>
          <tbody>
            {filteredTorches.map((t) => (
              <tr key={t.id} className="border-t border-line">
                <td className="px-4 py-2.5 font-mono text-bone">{t.id}</td>
                <td className="px-4 py-2.5">
                  <KindBadge kind={t.kind} />
                </td>
                <td className="px-4 py-2.5 font-mono text-dim">{t.options.join(" · ") || "—"}</td>
                <td className="max-w-md truncate px-4 py-2.5 text-ash">{t.rite || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
