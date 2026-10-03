import { NavLink, Outlet, useParams, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { useHearths, useLineage, useProphecyState, useGraphLibrary, useInvalidateRun } from "../../api/hooks"
import { StatusPill, hearthStatus } from "../../components/Badges"
import { api } from "../../api/client"
import { fmtDate } from "../../lib/format"
import { useRunStore } from "../../lib/runStore"
import { runAutoLoop } from "../../lib/autorun"
import { useQueryClient } from "@tanstack/react-query"
import type { Hearth, LineageRow, ProphecyState } from "../../api/types"

export interface HearthContext {
  hearth: Hearth
  lineage: LineageRow[]
  pid: string
  state: ProphecyState
}

export function HearthLayout() {
  const { hearthId } = useParams<{ hearthId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const invalidate = useInvalidateRun()
  const { data: hearths } = useHearths()
  const { data: lineage } = useLineage(hearthId)
  const { data: graphLib } = useGraphLibrary()
  const running = useRunStore((s) => s.running && s.hearth === hearthId)

  const hearth = hearths?.find((h) => h.id === hearthId)
  const currentPid = lineage?.[lineage.length - 1]?.id
  const { data: state } = useProphecyState(currentPid, { poll: running })

  if (!hearths || !lineage) {
    return <div className="p-7 text-[13px] text-dim">Loading…</div>
  }
  if (!hearth || !currentPid || !state) {
    return (
      <div className="p-7">
        <div className="text-[14px] text-ash">No hearth found with id {hearthId}.</div>
        <button onClick={() => navigate("/hearths")} className="mt-3 text-[13px] text-ember2">
          ← back to Hearths
        </button>
      </div>
    )
  }

  const toggleHalt = async () => {
    try {
      if (hearth.halted) {
        await api.resume(hearth.id)
        toast.success("resumed")
      } else {
        useRunStore.getState().stop()
        await api.halt(hearth.id)
        toast.success("halted")
      }
      invalidate(currentPid, hearth.id)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const resumeDriving = () => {
    if (!graphLib) return
    const fr = state.frontier.filter(Boolean)
    if (!fr.length) {
      toast.info("this generation has nothing left in its frontier")
      return
    }
    runAutoLoop(currentPid, hearth.id, graphLib.nodes, qc)
  }

  const ctx: HearthContext = { hearth, lineage, pid: currentPid, state }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-6 pt-4.5">
        <div className="text-[12px] text-dim">
          <NavLink to="/hearths" className="hover:text-ash">
            Hearths
          </NavLink>{" "}
          / {hearth.id}
        </div>
        <div className="mt-1.5 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 font-display text-[22px] font-[650]">
              {hearth.label || hearth.id}
              <StatusPill kind={hearthStatus(hearth.halted)} pulse={!hearth.halted}>
                {hearth.halted ? "halted" : "active"}
              </StatusPill>
            </div>
            <div className="mt-1 text-[13.5px] text-ash italic">{hearth.ember}</div>
          </div>
          <div className="flex shrink-0 gap-2">
            {!hearth.halted && !running && state.frontier.filter(Boolean).length > 0 && (
              <button
                onClick={resumeDriving}
                className="rounded-md bg-ember px-3.5 py-1.5 text-[13px] font-semibold text-[#1b1009] hover:bg-ember2"
              >
                Resume driving
              </button>
            )}
            <button
              onClick={toggleHalt}
              className="rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone"
            >
              {hearth.halted ? "Resume" : "Halt"}
            </button>
          </div>
        </div>

        <div className="mt-4 flex gap-7">
          <Stat label="generations" value={String(hearth.generations)} />
          <Stat label="capabilities" value={String(state.capabilities.length)} />
          <Stat
            label="disk"
            value={`${(hearth.diskused / 1e6).toFixed(1)} MB`}
            sub={hearth.diskcap ? `of ${(hearth.diskcap / 1e6).toFixed(0)} MB cap` : "no cap"}
          />
          <Stat label="lit at" value={fmtDate(hearth.born)} />
        </div>

        <nav className="mt-3.5 flex gap-1">
          <Tab to="." end label="Overview" />
          <Tab to="graph" label="Graph" />
          <Tab to="code" label="Code" count={state.tree.length || undefined} />
          <Tab to="activity" label="Activity" />
          <Tab to="settings" label="Settings" />
        </nav>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Outlet context={ctx} />
      </div>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="font-display text-[19px] font-[650] [font-variant-numeric:tabular-nums]">{value}</div>
      <div className="text-[11.5px] text-dim">
        {label}
        {sub ? ` · ${sub}` : ""}
      </div>
    </div>
  )
}

function Tab({ to, end, label, count }: { to: string; end?: boolean; label: string; count?: number }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `border-b-2 px-3.5 py-2 text-[13.5px] ${
          isActive ? "border-ember text-bone" : "border-transparent text-ash hover:text-bone"
        }`
      }
    >
      {label}
      {count !== undefined && <small className="ml-1 font-mono text-[10.5px] text-dim">{count}</small>}
    </NavLink>
  )
}
