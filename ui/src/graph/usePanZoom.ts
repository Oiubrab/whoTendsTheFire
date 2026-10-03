import { useEffect, useRef, useState } from "react"

const MIN_SCALE = 0.15
const MAX_SCALE = 4

export interface ViewState {
  x: number
  y: number
  scale: number
}

// Ported near-verbatim from the old UI's setupPanZoom(): wheel zooms
// toward the cursor (solve the translate so the same world point stays
// under the pointer), pointer drag pans, and a drag that actually moved
// the camera suppresses the click that would otherwise fire on release.
export function usePanZoom(svgRef: React.RefObject<SVGSVGElement | null>) {
  const [view, setView] = useState<ViewState>({ x: 0, y: 0, scale: 1 })
  // the wheel/pointer handlers below are attached once and read the
  // latest view via this ref rather than closing over `view` directly,
  // so they don't need to be torn down and reattached on every pan/zoom
  // frame. Synced in an effect, not during render, so it never touches
  // a ref while React is rendering.
  const viewRef = useRef(view)
  useEffect(() => {
    viewRef.current = view
  }, [view])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    let dragging = false
    let dragged = false
    let startX = 0
    let startY = 0
    let startViewX = 0
    let startViewY = 0

    const toSvgPoint = (clientX: number, clientY: number) => {
      const r = svg.getBoundingClientRect()
      return { x: clientX - r.left, y: clientY - r.top }
    }

    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault()
      const p = toSvgPoint(ev.clientX, ev.clientY)
      const { x, y, scale } = viewRef.current
      const worldX = (p.x - x) / scale
      const worldY = (p.y - y) / scale
      const factor = Math.exp(-ev.deltaY * 0.0015)
      const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor))
      setView({ x: p.x - worldX * nextScale, y: p.y - worldY * nextScale, scale: nextScale })
    }

    const onPointerDown = (ev: PointerEvent) => {
      if (ev.button !== 0) return
      dragging = true
      dragged = false
      startX = ev.clientX
      startY = ev.clientY
      startViewX = viewRef.current.x
      startViewY = viewRef.current.y
      svg.setPointerCapture(ev.pointerId)
      svg.classList.add("panning")
    }

    const onPointerMove = (ev: PointerEvent) => {
      if (!dragging) return
      const dx = ev.clientX - startX
      const dy = ev.clientY - startY
      if (!dragged && Math.hypot(dx, dy) > 3) dragged = true
      if (dragged) setView((v) => ({ ...v, x: startViewX + dx, y: startViewY + dy }))
    }

    const endDrag = () => {
      if (!dragging) return
      dragging = false
      svg.classList.remove("panning")
      if (dragged) {
        const suppress = (e: Event) => {
          e.stopPropagation()
          svg.removeEventListener("click", suppress, true)
        }
        svg.addEventListener("click", suppress, true)
      }
    }

    svg.addEventListener("wheel", onWheel, { passive: false })
    svg.addEventListener("pointerdown", onPointerDown)
    svg.addEventListener("pointermove", onPointerMove)
    svg.addEventListener("pointerup", endDrag)
    svg.addEventListener("pointercancel", endDrag)
    return () => {
      svg.removeEventListener("wheel", onWheel)
      svg.removeEventListener("pointerdown", onPointerDown)
      svg.removeEventListener("pointermove", onPointerMove)
      svg.removeEventListener("pointerup", endDrag)
      svg.removeEventListener("pointercancel", endDrag)
    }
  }, [svgRef])

  const reset = () => setView({ x: 0, y: 0, scale: 1 })
  return { view, reset }
}
