import type { GraphEdge, GraphNode } from "../api/types"

export const END_ID = "__end__"

export interface Point {
  x: number
  y: number
  vx: number
  vy: number
}

// Ported from the old UI's buildLayoutGraph(): a simple force simulation,
// run once up front, then static. Not physically accurate, just stable
// and readable -- nodes repel each other, edges pull their endpoints
// toward a resting length, and everything is pulled gently toward the
// center so the graph doesn't drift off canvas.
export function layoutGraph(nodes: GraphNode[], edges: GraphEdge[]): Record<string, Point> {
  const nodeIds = nodes.map((n) => n.id)
  const hasEnd = edges.some((e) => !e.dst)
  const ids = hasEnd ? [...nodeIds, END_ID] : nodeIds
  const pos: Record<string, Point> = {}

  ids.forEach((id, i) => {
    const angle = (i / ids.length) * 2 * Math.PI
    pos[id] = {
      x: 480 + 260 * Math.cos(angle) + (Math.random() - 0.5) * 20,
      y: 320 + 260 * Math.sin(angle) + (Math.random() - 0.5) * 20,
      vx: 0,
      vy: 0,
    }
  })

  const edgePairs = edges.map((e) => ({ src: e.src, dst: e.dst || END_ID }))

  for (let iter = 0; iter < 400; iter++) {
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = pos[ids[i]]
        const b = pos[ids[j]]
        let dx = a.x - b.x
        let dy = a.y - b.y
        const dist2 = dx * dx + dy * dy || 0.01
        const force = 9000 / dist2
        const dist = Math.sqrt(dist2)
        dx /= dist
        dy /= dist
        a.vx += dx * force
        a.vy += dy * force
        b.vx -= dx * force
        b.vy -= dy * force
      }
    }
    edgePairs.forEach((e) => {
      const a = pos[e.src]
      const b = pos[e.dst]
      if (!a || !b) return
      let dx = b.x - a.x
      let dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01
      const force = (dist - 170) * 0.012
      dx /= dist
      dy /= dist
      a.vx += dx * force
      a.vy += dy * force
      b.vx -= dx * force
      b.vy -= dy * force
    })
    ids.forEach((id) => {
      const p = pos[id]
      p.vx += (480 - p.x) * 0.0015
      p.vy += (320 - p.y) * 0.0015
      p.vx *= 0.82
      p.vy *= 0.82
      p.x += p.vx
      p.y += p.vy
    })
  }

  return pos
}

export function neighborsOf(edges: GraphEdge[], id: string): Set<string> {
  const out = new Set<string>()
  edges.forEach((e) => {
    if (e.src === id && e.dst) out.add(e.dst)
    if (e.dst === id) out.add(e.src)
  })
  return out
}
