import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { useHearths, useGraphLibrary } from "../api/hooks"
import { api } from "../api/client"
import { HearthCard } from "../components/HearthCard"
import { StatusPill } from "../components/Badges"
import { fmtDate } from "../lib/format"
import { useRunStore, type RunMode } from "../lib/runStore"
import { runAutoLoop } from "../lib/autorun"

const EXAMPLES = [
  "a CLI that renames photos by EXIF date",
  "a pantry tracker with expiry warnings",
  "a tiny status page for my home server",
]

const MODES: { id: RunMode; label: string; help: string }[] = [
  { id: "autonomous", label: "Autonomous", help: "Kindles every generation without asking" },
  { id: "approve", label: "Approve each generation", help: "Pauses before each new generation spawns" },
  { id: "step", label: "Step by step", help: "You drive every torch by hand from the Graph tab" },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: hearths } = useHearths()
  const { data: graphLib } = useGraphLibrary()
  const [invocation, setInvocation] = useState("")
  const [mode, setMode] = useState<RunMode>("approve")
  const [maxGens, setMaxGens] = useState("")
  const [diskCap, setDiskCap] = useState("")
  const [starting, setStarting] = useState(false)

  const running = (hearths ?? []).filter((h) => !h.halted)
  const halted = (hearths ?? []).filter((h) => h.halted)
  const recent = [...(hearths ?? [])].sort((a, b) => b.born.localeCompare(a.born)).slice(0, 6)

  const light = async () => {
    if (!invocation.trim()) {
      toast.error("say what to build first")
      return
    }
    setStarting(true)
    try {
      const body: Parameters<typeof api.begin>[0] = { invocation: invocation.trim(), graph: "g.found" }
      if (maxGens.trim()) body.maxproph = Number(maxGens)
      if (diskCap.trim()) body.diskcap = Number(diskCap) * 1_000_000
      const res = await api.begin(body)
      qc.invalidateQueries({ queryKey: ["hearths"] })
      useRunStore.getState().setRunMode(mode)
      setInvocation("")
      navigate(`/hearths/${res.hearth}/graph`)
      if (mode !== "step" && graphLib) {
        runAutoLoop(res.pid, res.hearth, graphLib.nodes, qc)
      }
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-7">
      <div className="rounded-xl border border-line bg-char">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Light a hearth</h2>
          <span className="text-[12px] text-dim">The ember is the one sentence every generation serves</span>
        </div>
        <div className="p-4">
          <textarea
            value={invocation}
            onChange={(e) => setInvocation(e.target.value)}
            placeholder="What do you want to build? e.g. a reading log where I paste a book title and it fetches the cover"
            rows={2}
            className="w-full resize-none rounded-lg border border-line2 bg-soot px-3.5 py-3 text-[15px] text-bone outline-none placeholder:text-dim focus:border-ember"
          />
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => setInvocation(ex)}
                className="rounded-full border border-dashed border-line2 px-2.5 py-0.5 text-[12px] text-ash hover:border-ash hover:text-bone"
              >
                {ex}
              </button>
            ))}
          </div>
          <div className="mt-3.5 flex flex-wrap items-center gap-2.5">
            <div className="inline-flex overflow-hidden rounded-md border border-line2">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  title={m.help}
                  onClick={() => setMode(m.id)}
                  className={`px-2.5 py-1 text-[12px] ${mode === m.id ? "bg-coal text-bone" : "text-ash hover:text-bone"}`}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <label className="inline-flex items-center gap-1.5 rounded-md border border-line2 px-2.5 py-1 text-[12px] text-ash">
              Stop after
              <input
                value={maxGens}
                onChange={(e) => setMaxGens(e.target.value.replace(/\D/g, ""))}
                placeholder="∞"
                className="w-10 bg-transparent text-center font-mono text-[11.5px] text-bone outline-none"
              />
              generations
            </label>
            <label className="inline-flex items-center gap-1.5 rounded-md border border-line2 px-2.5 py-1 text-[12px] text-ash">
              Disk cap
              <input
                value={diskCap}
                onChange={(e) => setDiskCap(e.target.value.replace(/\D/g, ""))}
                placeholder="∞"
                className="w-10 bg-transparent text-center font-mono text-[11.5px] text-bone outline-none"
              />
              MB
            </label>
            <div className="flex-1" />
            <button
              onClick={light}
              disabled={starting}
              className="rounded-md bg-ember px-4 py-1.5 text-[13px] font-semibold text-[#1b1009] hover:bg-ember2 disabled:opacity-50"
            >
              Light the hearth
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4.5 grid grid-cols-2 gap-3.5">
        <div className="rounded-xl border border-line bg-char">
          <div className="border-b border-line px-4 py-2.5">
            <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Running now</h2>
          </div>
          {running.length === 0 ? (
            <div className="p-4 text-[13px] text-dim">Nothing is building right now.</div>
          ) : (
            <div className="divide-y divide-line">
              {running.map((h) => (
                <AttentionRow key={h.id} hearth={h} kind="live" />
              ))}
            </div>
          )}
        </div>
        <div className="rounded-xl border border-line bg-char">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Needs your attention</h2>
            <span className="text-[12px] text-dim">{halted.length}</span>
          </div>
          {halted.length === 0 ? (
            <div className="p-4 text-[13px] text-dim">Nothing is halted.</div>
          ) : (
            <div className="divide-y divide-line">
              {halted.map((h) => (
                <AttentionRow key={h.id} hearth={h} kind="warn" />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4.5 rounded-xl border border-line bg-char">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Recent hearths</h2>
          <button onClick={() => navigate("/hearths")} className="text-[12px] text-ash hover:text-bone">
            All hearths
          </button>
        </div>
        {recent.length === 0 ? (
          <div className="p-4 text-[13px] text-dim">No hearths lit yet.</div>
        ) : (
          <div className="grid grid-cols-3 gap-3 p-3.5">
            {recent.map((h) => (
              <HearthCard key={h.id} hearth={h} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function AttentionRow({ hearth, kind }: { hearth: NonNullable<ReturnType<typeof useHearths>["data"]>[number]; kind: "live" | "warn" }) {
  const navigate = useNavigate()
  return (
    <div className="flex items-start gap-3.5 px-4 py-3">
      <span className={`mt-0.5 h-full w-[3px] self-stretch rounded ${kind === "live" ? "bg-ember" : "bg-warn"}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-bone">{hearth.label || hearth.id}</span>
          <StatusPill kind={kind} pulse={kind === "live"}>
            {kind === "live" ? "running" : "halted"}
          </StatusPill>
        </div>
        <div className="mt-0.5 truncate text-[12.5px] text-ash">
          generation {hearth.generations} · {hearth.ember}
        </div>
        <div className="mt-0.5 text-[11px] text-dim">{fmtDate(hearth.born)}</div>
      </div>
      <button
        onClick={() => navigate(`/hearths/${hearth.id}`)}
        className="shrink-0 rounded-md border border-line2 px-2.5 py-1 text-[12px] text-ash hover:text-bone"
      >
        Open
      </button>
    </div>
  )
}
