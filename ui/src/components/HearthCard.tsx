import { Link } from "react-router-dom"
import { useState, type MouseEvent } from "react"
import { toast } from "sonner"
import type { Hearth } from "../api/types"
import { StatusPill, hearthStatus } from "./Badges"
import { fmtBytes, fmtDate } from "../lib/format"
import { api } from "../api/client"
import { useInvalidateRun } from "../api/hooks"
import { RenameDialog } from "./RenameDialog"

export function HearthCard({ hearth }: { hearth: Hearth }) {
  const invalidate = useInvalidateRun()
  const [renaming, setRenaming] = useState(false)

  const toggleHalt = async (e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      if (hearth.halted) {
        await api.resume(hearth.id)
        toast.success(`${hearth.label || hearth.id} resumed`)
      } else {
        await api.halt(hearth.id)
        toast.success(`${hearth.label || hearth.id} halted`)
      }
      invalidate(undefined, hearth.id)
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  const openRename = (e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setRenaming(true)
  }

  return (
    <>
      <Link
        to={`/hearths/${hearth.id}`}
        className="block rounded-lg border border-line bg-char p-4 hover:border-line2"
      >
        <div className="flex items-start justify-between gap-2">
          <span className="font-medium text-bone">{hearth.label || hearth.id}</span>
          <StatusPill kind={hearthStatus(hearth.halted)} pulse={!hearth.halted}>
            {hearth.halted ? "halted" : "active"}
          </StatusPill>
        </div>
        <div className="mt-1 truncate text-[12.5px] italic text-ash">{hearth.ember}</div>
        <div className="mt-2.5 flex flex-wrap gap-2.5 text-[11px] text-dim">
          <span>
            {hearth.maxproph ? `${hearth.generations}/${hearth.maxproph} gens` : `${hearth.generations} gens`}
          </span>
          <span>
            {fmtBytes(hearth.diskused)} / {hearth.diskcap ? fmtBytes(hearth.diskcap) : "no cap"}
          </span>
          <span>{fmtDate(hearth.born)}</span>
        </div>
        <div className="mt-2.5 flex gap-1.5">
          <button
            onClick={toggleHalt}
            className="rounded border border-line2 px-2 py-0.5 text-[11px] text-ash hover:text-bone"
          >
            {hearth.halted ? "resume" : "halt"}
          </button>
          <button
            onClick={openRename}
            className="rounded border border-line2 px-2 py-0.5 text-[11px] text-ash hover:text-bone"
          >
            rename
          </button>
        </div>
      </Link>
      {renaming && (
        <RenameDialog hearth={hearth} onClose={() => setRenaming(false)} />
      )}
    </>
  )
}
