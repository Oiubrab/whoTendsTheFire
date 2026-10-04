import { Link } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useRunStore } from "../lib/runStore"
import { useHearths } from "../api/hooks"
import { api } from "../api/client"

// A persistent strip, visible from every screen, listing every hearth
// runner.py is actively driving -- server state via /api/events, not
// this tab's own doing, so it's accurate even for a run someone started
// from a different tab or that was already going when this one opened.
export function RunDock() {
  const runs = useRunStore((s) => s.runs)
  const { data: hearths } = useHearths()
  const rows = Object.values(runs).filter((r) => !r.pendingApproval)
  if (rows.length === 0) return null

  const stop = async (hearth: string) => {
    try {
      await api.runsStop(hearth)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="grid gap-px border-b border-line bg-line">
      {rows.map((r) => {
        const hearth = hearths?.find((h) => h.id === r.hearth)
        return (
          <div key={r.hearth} className="flex items-center gap-3 bg-[#17120e] px-5 py-2 text-[12.5px] text-ember2">
            <Loader2 size={13} className="animate-spin shrink-0" />
            <span className="truncate">
              building <strong className="font-medium text-bone">{hearth?.label || hearth?.ember || r.hearth}</strong>
              {r.status ? ` — ${r.status}` : ""}
            </span>
            <div className="flex-1" />
            <Link to={`/hearths/${r.hearth}/graph`} className="rounded border border-line2 px-2.5 py-1 text-ash hover:text-bone">
              watch
            </Link>
            <button onClick={() => stop(r.hearth)} className="rounded border border-line2 px-2.5 py-1 text-ash hover:text-bone">
              stop
            </button>
          </div>
        )
      })}
    </div>
  )
}
