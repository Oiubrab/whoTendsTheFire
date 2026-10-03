import { useEffect, useState } from "react"
import { Command } from "cmdk"
import { useNavigate } from "react-router-dom"
import { useHearths } from "../api/hooks"

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { data: hearths } = useHearths()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((o) => !o)
      }
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [])

  const go = (path: string) => {
    navigate(path)
    setOpen(false)
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[14vh]"
      onClick={() => setOpen(false)}
    >
      <Command
        className="w-full max-w-lg overflow-hidden rounded-xl border border-line2 bg-char shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        shouldFilter
      >
        <Command.Input
          autoFocus
          placeholder="Jump to a hearth, or an action…"
          className="w-full border-b border-line bg-transparent px-4 py-3.5 text-[14px] text-bone placeholder:text-dim outline-none"
        />
        <Command.List className="max-h-[360px] overflow-y-auto p-2">
          <Command.Empty className="px-3 py-6 text-center text-[13px] text-dim">No matches.</Command.Empty>
          <Command.Group heading="Go to" className="px-2 py-1 text-[11px] uppercase tracking-wider text-dim [&_[cmdk-group-heading]]:px-1 [&_[cmdk-group-heading]]:pb-1.5">
            <Command.Item onSelect={() => go("/")} className="cursor-pointer rounded-md px-3 py-2 text-[13px] text-bone data-[selected=true]:bg-coal">
              Dashboard
            </Command.Item>
            <Command.Item onSelect={() => go("/hearths")} className="cursor-pointer rounded-md px-3 py-2 text-[13px] text-bone data-[selected=true]:bg-coal">
              All hearths
            </Command.Item>
            <Command.Item onSelect={() => go("/library")} className="cursor-pointer rounded-md px-3 py-2 text-[13px] text-bone data-[selected=true]:bg-coal">
              Library
            </Command.Item>
            <Command.Item onSelect={() => go("/system")} className="cursor-pointer rounded-md px-3 py-2 text-[13px] text-bone data-[selected=true]:bg-coal">
              System
            </Command.Item>
          </Command.Group>
          {hearths && hearths.length > 0 && (
            <Command.Group heading="Hearths" className="px-2 py-1 text-[11px] uppercase tracking-wider text-dim [&_[cmdk-group-heading]]:px-1 [&_[cmdk-group-heading]]:pb-1.5">
              {hearths.map((h) => (
                <Command.Item
                  key={h.id}
                  value={`${h.label || h.id} ${h.ember}`}
                  onSelect={() => go(`/hearths/${h.id}`)}
                  className="cursor-pointer rounded-md px-3 py-2 text-[13px] text-bone data-[selected=true]:bg-coal"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate">{h.label || h.id}</span>
                    <span className="shrink-0 font-mono text-[10.5px] text-dim">
                      {h.halted ? "halted" : "active"}
                    </span>
                  </div>
                </Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  )
}
