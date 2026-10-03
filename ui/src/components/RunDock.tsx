import { Link } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { useRunStore } from "../lib/runStore"
import { useProphecyState } from "../api/hooks"

// A persistent strip, visible from every screen, showing whatever this
// tab is currently auto-driving. Matches the Dashboard mockup's "Running
// now" idea but lives in the shell so it is never scrolled out of view.
export function RunDock() {
  const running = useRunStore((s) => s.running)
  const pid = useRunStore((s) => s.pid)
  const hearth = useRunStore((s) => s.hearth)
  const status = useRunStore((s) => s.statusMessage)
  const stop = useRunStore((s) => s.stop)
  const { data: state } = useProphecyState(running ? pid ?? undefined : undefined)

  if (!running || !pid) return null

  return (
    <div className="flex items-center gap-3 border-b border-line bg-[#17120e] px-5 py-2 text-[12.5px] text-ember2">
      <Loader2 size={13} className="animate-spin" />
      <span className="truncate">
        building <strong className="font-medium text-bone">{state?.ember ?? pid}</strong>
        {status ? ` — ${status}` : ""}
      </span>
      <div className="flex-1" />
      <Link to={`/hearths/${hearth}/graph`} className="rounded border border-line2 px-2.5 py-1 text-ash hover:text-bone">
        watch
      </Link>
      <button onClick={stop} className="rounded border border-line2 px-2.5 py-1 text-ash hover:text-bone">
        stop
      </button>
    </div>
  )
}
