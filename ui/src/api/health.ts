import { useQuery } from "@tanstack/react-query"

export interface Health {
  bridge: boolean
  port: number
  ollama: boolean
  model: string
  diskused: number
}

async function fetchHealth(): Promise<Health> {
  const res = await fetch("/api/health")
  return res.json()
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 10000 })
}
