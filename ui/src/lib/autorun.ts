import type { QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "../api/client"
import type { GraphNode, ProphecyState } from "../api/types"
import { useRunStore } from "./runStore"

// Ported from the old single-file UI's autoRun(): walks a prophecy one
// torch at a time, same decision tree per torch kind. The engine itself
// still lives in the browser in Phase 1 -- moving it server-side so a
// closed tab doesn't pause the lineage is Phase 2.
const MAX_STEPS = 60

export async function runAutoLoop(pid: string, hearth: string, nodes: GraphNode[], qc: QueryClient) {
  const store = useRunStore.getState()
  if (store.running && store.pid === pid) return
  store.start(pid, hearth)

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["state", pid] })
    qc.invalidateQueries({ queryKey: ["files", pid] })
    qc.invalidateQueries({ queryKey: ["lineage", hearth] })
    qc.invalidateQueries({ queryKey: ["hearths"] })
  }

  const getState = async (): Promise<ProphecyState> => {
    const s = await api.state(pid)
    qc.setQueryData(["state", pid], s)
    return s
  }

  try {
    let state = await getState()
    let curPid = pid

    for (let step = 0; step < MAX_STEPS; step++) {
      if (useRunStore.getState().stopRequested) {
        useRunStore.getState().setStatus("stopped")
        break
      }
      const frontier = state.frontier.filter(Boolean)
      if (!frontier.length) {
        useRunStore.getState().setStatus("prophecy complete")
        break
      }

      const id = frontier[0]
      const node = nodes.find((n) => n.id === id)
      useRunStore.getState().setWorking(id)
      if (useRunStore.getState().pid !== curPid) useRunStore.getState().setPid(curPid)

      if (!node) {
        // the library changed under a live walk (edge case, not expected
        // in normal use) -- stop rather than throw blind at an unknown id
        useRunStore.getState().setStatus(`unknown torch ${id}, stopping`)
        break
      }

      if (node.kind === "authoring") {
        useRunStore.getState().setStatus(`${id}: the local model is writing the code…`)
        try {
          const r = await api.authorize(curPid, id)
          useRunStore.getState().setStatus(`${id}: wrote ${r.path} (${r.bytes} bytes)`)
        } catch (e) {
          useRunStore.getState().setStatus(`${id}: ${(e as Error).message}`)
        }
        const lit = await api.light(curPid, id, node.options[0])
        state = lit.state
        invalidate()
      } else if (node.kind === "kindling") {
        useRunStore.getState().setStatus(`${id}: asking what to build next…`)
        const p = await api.propose(curPid, id)
        if (!p.invocation) {
          useRunStore.getState().setStatus("nothing further proposed — lineage ends here")
          await api.light(curPid, id, "decline")
          invalidate()
          break
        }
        const invocation = p.invocation
        let graphChoice: string

        if (useRunStore.getState().runMode === "approve") {
          useRunStore.getState().setStatus(`${id}: proposed — waiting for your approval…`)
          const choice = await useRunStore.getState().requestApproval({
            pid: curPid,
            torch: id,
            invocation,
            offerable: state.offerable,
          })
          if (choice.action === "reject") {
            useRunStore.getState().setStatus("generation declined by you — lineage ends here")
            await api.light(curPid, id, "decline")
            invalidate()
            break
          }
          graphChoice = choice.graph
        } else {
          // "choose.graph" literally, not `id` (kindle.next's own id) --
          // choosegraph's torch param selects WHICH torch's rite/options
          // to read, and kindle.next's options are written/decline, not
          // the 8 graph ids. Passing id here silently corrupted every
          // spawned generation's graph field with the string "written".
          const c = await api.choosegraph(curPid, "choose.graph", invocation)
          graphChoice = c.option
        }

        useRunStore.getState().setPending(invocation)
        await api.light(curPid, id, "written")
        useRunStore.getState().setStatus(`kindling ${graphChoice}: ${invocation}`)
        const spawned = await api.kindle(curPid, invocation, graphChoice)
        await api.light(curPid, "choose.graph", graphChoice)
        useRunStore.getState().setPending(null)
        curPid = spawned.pid
        state = spawned.state
        useRunStore.getState().setPid(curPid)
        invalidate()
        toast.success(`generation ${spawned.state.generation} kindled: ${graphChoice}`)
      } else if (node.kind === "validation") {
        useRunStore.getState().setStatus(`${id}: running the check…`)
        const lit = await api.light(curPid, id, node.options[0])
        state = lit.state
        invalidate()
      } else {
        useRunStore.getState().setStatus(`${id}: choosing…`)
        const c = await api.choose(curPid, id)
        const lit = await api.light(curPid, id, c.option)
        state = lit.state
        invalidate()
      }
      useRunStore.getState().setWorking(null)
    }
  } catch (e) {
    useRunStore.getState().setStatus(`error: ${(e as Error).message}`)
    toast.error((e as Error).message)
  } finally {
    useRunStore.getState().setWorking(null)
    useRunStore.getState().setRunning(false)
  }
}
