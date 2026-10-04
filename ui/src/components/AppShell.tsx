import type { ReactNode } from "react"
import { NavLink, Outlet } from "react-router-dom"
import { Flame, LayoutDashboard, Library as LibraryIcon, Settings2 } from "lucide-react"
import { useHearths } from "../api/hooks"
import { useHealth } from "../api/health"
import { useEventStream } from "../lib/useEventStream"
import { useRunStore } from "../lib/runStore"
import { CommandPalette } from "./CommandPalette"
import { RunDock } from "./RunDock"
import { Toaster } from "./Toast"
import { ApprovalDialog } from "./ApprovalDialog"

function NavItem({ to, icon, label, count }: { to: string; icon: ReactNode; label: string; count?: number }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center justify-between gap-2 rounded-md px-2.5 py-2 text-[13px] ${
          isActive
            ? "bg-coal text-bone shadow-[inset_2px_0_0_var(--color-ember)]"
            : "text-ash hover:text-bone"
        }`
      }
    >
      <span className="flex items-center gap-2.5">
        {icon}
        {label}
      </span>
      {count !== undefined && <small className="font-mono text-[10.5px] text-dim">{count}</small>}
    </NavLink>
  )
}

function Dot({ ok }: { ok: boolean | undefined }) {
  return (
    <span
      className={`inline-block h-[7px] w-[7px] rounded-full ${
        ok === undefined ? "bg-ash" : ok ? "bg-pass" : "bg-fail"
      }`}
    />
  )
}

export function AppShell() {
  useEventStream()
  const { data: hearths } = useHearths()
  const { data: health } = useHealth()
  const liveCount = Object.keys(useRunStore((s) => s.runs)).length

  return (
    <div className="flex h-dvh bg-soot text-bone">
      <aside className="flex w-[206px] shrink-0 flex-col gap-1 border-r border-line bg-char p-3">
        <div className="flex items-center gap-2 px-2 pb-4 font-display text-[15px] font-[650]">
          <Flame size={18} className="text-ember" fill="currentColor" />
          whoTendsTheFire
        </div>
        <NavItem to="/" icon={<LayoutDashboard size={15} />} label="Dashboard" />
        <NavItem to="/hearths" icon={<Flame size={15} />} label="Hearths" count={hearths?.length} />
        <NavItem to="/library" icon={<LibraryIcon size={15} />} label="Library" />
        <NavItem to="/system" icon={<Settings2 size={15} />} label="System" />
        <div className="flex-1" />
        <div className="grid gap-[7px] border-t border-line px-2 pt-3 text-xs text-ash">
          <div className="flex justify-between gap-2">
            <span className="flex items-center gap-1.5">
              <Dot ok={health?.bridge} />
              Bridge
            </span>
            <span className="font-mono">{health?.port ?? "..."}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="flex items-center gap-1.5">
              <Dot ok={health?.ollama} />
              Ollama
            </span>
            <span className="truncate font-mono" title={health?.model}>
              {health?.model ?? "..."}
            </span>
          </div>
          {liveCount > 0 && (
            <div className="flex justify-between gap-2">
              <span className="flex items-center gap-1.5">
                <Dot ok={true} />
                Running
              </span>
              <span className="font-mono">{liveCount}</span>
            </div>
          )}
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <RunDock />
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <CommandPalette />
      <ApprovalDialog />
      <Toaster />
    </div>
  )
}
