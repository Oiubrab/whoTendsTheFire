import { useOutletContext } from "react-router-dom"
import { useState } from "react"
import { toast } from "sonner"
import type { HearthContext } from "./HearthLayout"
import { api } from "../../api/client"
import { useInvalidateRun } from "../../api/hooks"
import { fmtDate } from "../../lib/format"

export default function Settings() {
  const { hearth } = useOutletContext<HearthContext>()
  const [label, setLabel] = useState(hearth.label)
  const invalidate = useInvalidateRun()

  const saveLabel = async () => {
    try {
      await api.label(hearth.id, label.trim())
      invalidate(undefined, hearth.id)
      toast.success("saved")
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const toggleHalt = async () => {
    try {
      if (hearth.halted) await api.resume(hearth.id)
      else await api.halt(hearth.id)
      invalidate(undefined, hearth.id)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-6">
      <div className="rounded-xl border border-line bg-char p-5">
        <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Label</h2>
        <div className="mt-2.5 flex gap-2">
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={hearth.id}
            className="flex-1 rounded-md border border-line2 bg-soot px-3 py-1.5 text-[13.5px] text-bone outline-none focus:border-ember"
          />
          <button onClick={saveLabel} className="rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone">
            Save
          </button>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-char p-5">
        <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Halt</h2>
        <p className="mt-1.5 text-[13px] text-ash">
          A halted hearth refuses every further kindling step -- the lineage stays exactly as it is, preserved for
          inspection, until resumed.
        </p>
        <button
          onClick={toggleHalt}
          className="mt-3 rounded-md border border-line2 px-3.5 py-1.5 text-[13px] text-ash hover:text-bone"
        >
          {hearth.halted ? "Resume this hearth" : "Halt this hearth"}
        </button>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-char p-5">
        <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Caps</h2>
        <p className="mt-1.5 text-[12.5px] text-dim">
          Set once at creation. Editing an existing hearth's caps needs a backend endpoint that doesn't exist yet.
        </p>
        <dl className="mt-3 grid grid-cols-2 gap-y-2 text-[13px]">
          <dt className="text-ash">Disk cap</dt>
          <dd className="font-mono">{hearth.diskcap ? `${(hearth.diskcap / 1e6).toFixed(0)} MB` : "unlimited"}</dd>
          <dt className="text-ash">Generation cap</dt>
          <dd className="font-mono">{hearth.maxproph || "unlimited"}</dd>
          <dt className="text-ash">Library</dt>
          <dd className="font-mono">{hearth.lib}</dd>
          <dt className="text-ash">Evolution</dt>
          <dd className="font-mono">{hearth.evolution ? "yes" : "no"}</dd>
          <dt className="text-ash">Hearth id</dt>
          <dd className="font-mono">{hearth.id}</dd>
          <dt className="text-ash">Lit</dt>
          <dd className="font-mono">{fmtDate(hearth.born)}</dd>
        </dl>
      </div>
    </div>
  )
}
