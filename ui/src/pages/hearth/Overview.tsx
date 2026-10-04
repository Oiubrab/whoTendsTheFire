import { useOutletContext } from "react-router-dom"
import { useState } from "react"
import type { HearthContext } from "./HearthLayout"
import { GraphChip } from "../../components/Badges"

export default function Overview() {
  const { hearth, lineage, state } = useOutletContext<HearthContext>()
  const [showFull, setShowFull] = useState(false)
  const frontierOpen = state.frontier.filter(Boolean).length > 0
  const lastCheckFailed = state.lastcheck.torch && state.lastcheck.option === "fail"

  const lastTrail = state.trail[state.trail.length - 1]
  const declined = lastTrail?.torch === "kindle.next" && lastTrail?.option === "decline"
  const reason = state.endreason
  const erroredOut = reason.startsWith("error:")
  const stuck = reason.startsWith("stuck:")
  const ceiling = reason.includes("step ceiling")
  const stoppedByUser = reason.startsWith("stopped after")

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      {(hearth.halted || !frontierOpen) && (
        <div className="flex gap-4 rounded-xl border border-[#4a2620] bg-failbg p-4">
          <span className="w-[3px] shrink-0 self-stretch rounded bg-fail" />
          <div className="min-w-0 flex-1">
            <h3 className="text-[14.5px] font-semibold text-bone">
              {lastCheckFailed
                ? `Stopped at generation ${hearth.generations}: a check failed`
                : erroredOut
                  ? `Stopped at generation ${hearth.generations}: an error`
                  : stuck
                    ? `Stopped at generation ${hearth.generations}: a repair loop didn't converge`
                    : ceiling
                      ? `Stopped at generation ${hearth.generations}: hit the step ceiling`
                      : hearth.halted
                        ? `Halted at generation ${hearth.generations}`
                        : declined
                          ? `Lineage ends: nothing further proposed`
                          : `This generation's walk has nothing left to do`}
            </h3>
            {lastCheckFailed ? (
              <>
                <div className="mt-1 text-[13px] text-ash">
                  <span className="font-mono text-[12px] text-fail">{state.lastcheck.torch}</span> failed. The
                  lineage did not reach its next kindling step.
                </div>
                <pre
                  className={`mt-2 overflow-x-auto rounded-md bg-soot px-3 py-2 font-mono text-[11.5px] text-[#f1b2a8] whitespace-pre-wrap ${showFull ? "" : "max-h-24 overflow-y-hidden"}`}
                >
                  {state.lastcheck.output}
                </pre>
                {state.lastcheck.output.length > 200 && (
                  <button onClick={() => setShowFull((v) => !v)} className="mt-1.5 text-[12px] text-ember2">
                    {showFull ? "show less" : "show full output"}
                  </button>
                )}
              </>
            ) : erroredOut || stuck || ceiling ? (
              <div className="mt-1 font-mono text-[12.5px] text-ash">{reason}</div>
            ) : hearth.halted ? (
              <div className="mt-1 text-[13px] text-ash">
                {stoppedByUser ? "You stopped it mid-generation. " : ""}
                You halted this hearth. Resume from the header above to let it keep kindling.
              </div>
            ) : declined ? (
              <div className="mt-1 text-[13px] text-ash">
                The model was asked what to build next and declined -- it judged nothing further worth doing,
                given what already exists.
              </div>
            ) : (
              <div className="mt-1 text-[13px] text-ash">
                No torch in the frontier can light, and this generation predates end-reason tracking, so the exact
                cause wasn't recorded.
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-5 rounded-xl border border-line bg-char">
        <div className="border-b border-line px-4 py-2.5">
          <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Generations</h2>
        </div>
        <div>
          {[...lineage].reverse().map((row) => (
            <GenRow key={row.id} row={row} current={row.id === lineage[lineage.length - 1].id} />
          ))}
        </div>
      </div>

      <div className="mt-5 rounded-xl border border-line bg-char">
        <div className="border-b border-line px-4 py-2.5">
          <h2 className="text-[12px] font-semibold tracking-wide text-ash uppercase">Capabilities earned</h2>
        </div>
        <div className="flex flex-wrap gap-1.5 p-4">
          {state.capabilities.length === 0 ? (
            <span className="text-[13px] text-dim">none yet</span>
          ) : (
            state.capabilities.map((c) => (
              <span key={c} className="rounded border border-line bg-coal px-1.5 py-0.5 font-mono text-[11px] text-ash">
                {c}
              </span>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function GenRow({ row, current }: { row: HearthContext["lineage"][number]; current: boolean }) {
  return (
    <div className={`flex items-center gap-3.5 border-b border-line px-4 py-3 last:border-0 ${current ? "bg-coal" : ""}`}>
      <span className={`font-display text-[17px] font-[650] ${current ? "text-ember2" : "text-ash"}`}>
        {row.generation}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] text-bone">{row.invocation}</div>
        <div className="mt-0.5 flex items-center gap-2 text-[11.5px] text-dim">
          <GraphChip id={row.graph} />
          {row.parent && <span className="font-mono">daughter of {row.parent}</span>}
        </div>
      </div>
    </div>
  )
}
