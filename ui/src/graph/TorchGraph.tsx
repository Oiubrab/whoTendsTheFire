import { useMemo, useRef } from "react"
import type { GraphEdge, GraphNode } from "../api/types"
import { END_ID, layoutGraph, neighborsOf } from "./layout"
import { usePanZoom } from "./usePanZoom"

const KIND_COLOR: Record<string, string> = {
  decision: "var(--color-k-decision)",
  action: "var(--color-k-action)",
  validation: "var(--color-k-validation)",
  kindling: "var(--color-k-kindling)",
  authoring: "var(--color-k-authoring)",
}

interface TorchGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  lit: Set<string>
  frontier: Set<string>
  working?: string | null
  selectedId?: string | null
  onSelect?: (node: GraphNode) => void
}

// The torch view, ported from the old single-file UI's render()/
// buildLayoutGraph()/setupPanZoom(), kept visually identical on purpose
// -- this was the one part of the old UI that worked. The only real
// change is that it is now fed a SCOPED node/edge set (one graph, not
// all nine merged) by the caller, and clicking selects into an inspector
// panel instead of immediately acting.
export function TorchGraph({ nodes, edges, lit, frontier, working, selectedId, onSelect }: TorchGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const { view, reset } = usePanZoom(svgRef)

  const pos = useMemo(() => layoutGraph(nodes, edges), [nodes, edges])
  const neighborSet = useMemo(() => {
    const set = new Set<string>()
    const seeds = new Set([...lit, ...frontier])
    seeds.forEach((id) => neighborsOf(edges, id).forEach((n) => set.add(n)))
    return set
  }, [edges, lit, frontier])
  const ended = frontier.has("")

  return (
    <div className="relative h-full w-full overflow-hidden bg-[radial-gradient(circle_at_45%_40%,#1c1510_0%,var(--color-soot)_70%)]">
      <svg
        ref={svgRef}
        className="block h-full w-full touch-none [&.panning]:cursor-grabbing"
        style={{ cursor: "grab" }}
      >
        <g transform={`translate(${view.x},${view.y}) scale(${view.scale})`}>
          {edges.map((e, i) => {
            const dstId = e.dst || END_ID
            const a = pos[e.src]
            const b = pos[dstId]
            if (!a || !b) return null
            const hot = lit.has(e.src) && (lit.has(dstId) || frontier.has(dstId))
            const mx = (a.x + b.x) / 2
            const my = (a.y + b.y) / 2
            return (
              <g key={`${e.src}-${e.label}-${i}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={hot ? "var(--color-gedge-hot)" : "var(--color-gedge)"}
                  strokeWidth={hot ? 2 : 1.5}
                />
                <text x={mx} y={my - 4} fontSize={9} fill="var(--color-dim)" textAnchor="middle" className="font-mono">
                  {e.label}
                </text>
              </g>
            )
          })}

          {pos[END_ID] && (
            <g transform={`translate(${pos[END_ID].x},${pos[END_ID].y})`}>
              <circle
                r={8}
                fill={ended ? "var(--color-lit)" : "#0f0c09"}
                stroke={ended ? "var(--color-lit-glow)" : "var(--color-gedge)"}
                strokeWidth={1.5}
                style={ended ? { filter: "drop-shadow(0 0 10px var(--color-lit-glow))" } : undefined}
              />
              <text y={20} fontSize={11} fill="var(--color-bone)" textAnchor="middle">
                end
              </text>
            </g>
          )}

          {nodes.map((n) => {
            const p = pos[n.id]
            if (!p) return null
            const isLit = lit.has(n.id)
            const isFrontier = frontier.has(n.id)
            const isNeighbor = neighborSet.has(n.id) && !isLit && !isFrontier
            const isWorking = working === n.id
            const isSelected = selectedId === n.id

            let fill = "var(--color-unlit)"
            let stroke = KIND_COLOR[n.kind] ?? "var(--color-unlit)"
            if (isNeighbor) {
              fill = "#2a2118"
              stroke = "var(--color-neighbor)"
            }
            if (isFrontier) {
              fill = "#3a2410"
              stroke = "var(--color-gfrontier)"
            }
            if (isLit) {
              fill = "var(--color-lit)"
              stroke = "var(--color-lit-glow)"
            }

            const parts = n.id.split(".").map((part) => (part.length > 9 ? part.slice(0, 8) + "…" : part))
            const startY = 4 - (parts.length - 1) * 6

            return (
              <g
                key={n.id}
                transform={`translate(${p.x},${p.y})`}
                className={isFrontier || onSelect ? "cursor-pointer" : ""}
                onClick={(ev) => {
                  ev.stopPropagation()
                  onSelect?.(n)
                }}
              >
                <circle
                  r={26}
                  fill={fill}
                  stroke={isSelected ? "var(--color-bone)" : stroke}
                  strokeWidth={isSelected ? 3 : 2}
                  style={{
                    filter: isLit
                      ? "drop-shadow(0 0 10px var(--color-lit-glow))"
                      : isFrontier
                        ? "drop-shadow(0 0 8px var(--color-gfrontier))"
                        : undefined,
                    animation: isWorking ? "torch-working 0.9s ease-in-out infinite" : undefined,
                  }}
                />
                <text y={-32} fontSize={9} fill="var(--color-ash)" textAnchor="middle" letterSpacing="0.6" className="font-mono uppercase">
                  {n.kind}
                </text>
                <text y={startY} fontSize={10} textAnchor="middle" fill={isLit || isFrontier ? "#1b1009" : "var(--color-bone)"}>
                  {parts.map((part, i) => (
                    <tspan key={i} x={0} dy={i === 0 ? 0 : 12}>
                      {part}
                    </tspan>
                  ))}
                </text>
              </g>
            )
          })}
        </g>
      </svg>

      <div className="absolute bottom-3 left-3.5 flex gap-3 rounded-md bg-[rgba(17,13,10,0.85)] px-2.5 py-1.5 text-[11px] text-ash">
        {Object.entries(KIND_COLOR).map(([kind, color]) => (
          <span key={kind} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: color }} />
            {kind}
          </span>
        ))}
      </div>
      <button
        onClick={reset}
        className="absolute right-3.5 bottom-3 rounded-md border border-line2 bg-char/90 px-2.5 py-1 text-[11px] text-ash hover:text-bone"
      >
        Fit
      </button>
    </div>
  )
}
