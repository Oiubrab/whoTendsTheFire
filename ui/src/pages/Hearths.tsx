import { useMemo, useState } from "react"
import { useHearths } from "../api/hooks"
import { HearthCard } from "../components/HearthCard"

type Filter = "all" | "active" | "halted"

export default function Hearths() {
  const { data: hearths } = useHearths()
  const [q, setQ] = useState("")
  const [filter, setFilter] = useState<Filter>("all")

  const filtered = useMemo(() => {
    let rows = hearths ?? []
    if (filter === "active") rows = rows.filter((h) => !h.halted)
    if (filter === "halted") rows = rows.filter((h) => h.halted)
    if (q.trim()) {
      const needle = q.trim().toLowerCase()
      rows = rows.filter(
        (h) => h.id.includes(needle) || h.label.toLowerCase().includes(needle) || h.ember.toLowerCase().includes(needle),
      )
    }
    return [...rows].sort((a, b) => b.born.localeCompare(a.born))
  }, [hearths, q, filter])

  return (
    <div className="mx-auto max-w-5xl px-6 py-7">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-display text-[22px] font-[650]">Hearths</h1>
        <div className="flex items-center gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search hearths…"
            className="w-56 rounded-md border border-line2 bg-char px-3 py-1.5 text-[13px] text-bone outline-none placeholder:text-dim focus:border-ember"
          />
          <div className="inline-flex overflow-hidden rounded-md border border-line2">
            {(["all", "active", "halted"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2.5 py-1.5 text-[12px] capitalize ${filter === f ? "bg-coal text-bone" : "text-ash hover:text-bone"}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-1 text-[12.5px] text-dim">
        {hearths?.length ?? 0} total · {filtered.length} shown
      </div>

      {filtered.length === 0 ? (
        <div className="mt-8 rounded-xl border border-dashed border-line2 p-10 text-center text-[13.5px] text-dim">
          No hearths match.
        </div>
      ) : (
        <div className="mt-5 grid grid-cols-3 gap-3.5">
          {filtered.map((h) => (
            <HearthCard key={h.id} hearth={h} />
          ))}
        </div>
      )}
    </div>
  )
}
