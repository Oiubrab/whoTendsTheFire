import { useMemo, useState } from "react"
import { useOutletContext } from "react-router-dom"
import type { HearthContext } from "./HearthLayout"
import { useFiles, useGitLog } from "../../api/hooks"
import { api } from "../../api/client"
import { ChevronRight } from "lucide-react"

export default function Code() {
  const { pid } = useOutletContext<HearthContext>()
  const { data } = useFiles(pid)
  const [openDirs, setOpenDirs] = useState<Set<string>>(new Set())
  const [openFile, setOpenFile] = useState<string | null>(null)
  const { data: log } = useGitLog(pid)
  const [diff, setDiff] = useState<{ hash: string; text: string } | null>(null)

  const byDir = useMemo(() => {
    if (!data) return {}
    const groups: Record<string, string[]> = {}
    Object.keys(data.files)
      .sort()
      .forEach((name) => {
        const i = name.lastIndexOf("/")
        const dir = i === -1 ? "." : name.slice(0, i)
        ;(groups[dir] ??= []).push(name)
      })
    return groups
  }, [data])

  const dirs = Object.keys(byDir).sort()

  const toggleDir = (dir: string) => {
    setOpenDirs((prev) => {
      const next = new Set(prev)
      if (next.has(dir)) next.delete(dir)
      else next.add(dir)
      return next
    })
  }

  const showDiff = async (hash: string) => {
    const r = await api.gitshow(pid, hash)
    setDiff({ hash, text: r.diff || "(empty commit — nothing changed)" })
  }

  if (!data) return <div className="p-7 text-[13px] text-dim">Loading…</div>

  return (
    <div className="grid h-full grid-cols-[320px_1fr_340px]">
      <div className="overflow-y-auto border-r border-line p-3">
        <h2 className="mb-2 px-1 text-[12px] font-semibold tracking-wide text-ash uppercase">
          Files <span className="font-normal text-dim">{Object.keys(data.files).length}</span>
        </h2>
        {dirs.length === 0 ? (
          <div className="px-1 text-[13px] text-dim">nothing written yet</div>
        ) : (
          dirs.map((dir) => {
            const open = openDirs.has(dir) || dirs.length === 1
            return (
              <div key={dir} className="mb-0.5">
                <button
                  onClick={() => toggleDir(dir)}
                  className="flex w-full items-center gap-1 rounded px-1 py-1 text-left font-mono text-[11.5px] text-k-authoring hover:bg-coal"
                >
                  <ChevronRight size={11} className={`shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
                  {dir}/
                </button>
                {open &&
                  byDir[dir].map((name) => {
                    const base = name.slice(name.lastIndexOf("/") + 1)
                    const selected = openFile === name
                    return (
                      <button
                        key={name}
                        onClick={() => setOpenFile(name)}
                        className={`block w-full truncate rounded py-1 pr-2 pl-6 text-left font-mono text-[11.5px] hover:bg-coal ${
                          selected ? "text-ember2" : "text-ash"
                        }`}
                      >
                        {base}
                      </button>
                    )
                  })}
              </div>
            )
          })
        )}
      </div>

      <div className="overflow-auto border-r border-line">
        {openFile ? (
          <>
            <div className="sticky top-0 border-b border-line bg-char px-4 py-2 font-mono text-[12px] text-ember2">
              {openFile}
            </div>
            <pre className="p-4 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-bone">
              {data.files[openFile]}
            </pre>
          </>
        ) : (
          <div className="p-7 text-[13px] text-dim">Select a file to view it.</div>
        )}
      </div>

      <div className="overflow-y-auto p-3">
        <h2 className="mb-2 px-1 text-[12px] font-semibold tracking-wide text-ash uppercase">History</h2>
        <div className="grid gap-0.5">
          {(log?.commits ?? []).map((c) => (
            <button
              key={c.hash}
              onClick={() => showDiff(c.hash)}
              className={`border-b border-line px-1 py-1.5 text-left font-mono text-[11.5px] hover:text-bone ${
                diff?.hash === c.hash ? "text-bone" : "text-ash"
              }`}
            >
              <span className="mr-1.5 text-ember2">{c.hash.slice(0, 8)}</span>
              {c.date.slice(0, 16)} {c.subject}
            </button>
          ))}
          {(!log || log.commits.length === 0) && <div className="px-1 text-[13px] text-dim">no commits yet</div>}
        </div>
        {diff && (
          <pre className="mt-3 max-h-[50vh] overflow-auto rounded-md border border-line bg-soot p-2.5 font-mono text-[11px] whitespace-pre-wrap text-[#d8c98a]">
            {diff.text}
          </pre>
        )}
      </div>
    </div>
  )
}
