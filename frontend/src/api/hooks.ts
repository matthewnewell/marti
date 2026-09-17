import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  ChatMessage,
  ChatResult,
  DepotJournalEntry,
  ProjectDetail,
  ProjectSummary,
  Tension,
} from './types'

// Conway's Depot is called directly from the browser here (not proxied through this app's own
// backend) — same reasoning as the standalone embed widget: the Journal is the Depot's data,
// this is just a native-React rendering of it instead of the vanilla-JS widget (which renders
// as an independent floating overlay, incompatible with sharing AppLayout's own docked tab
// panel — see JournalPanel.tsx's own docstring). Depot's CORS is already open for this.
const DEPOT_URL = 'http://localhost:8090'

export function useDepotJournal(depotProjectId: string) {
  return useQuery({
    queryKey: ['depot-journal', depotProjectId],
    queryFn: async () => {
      const r = await fetch(`${DEPOT_URL}/api/projects/${depotProjectId}/journal`)
      const data = (await r.json()) as { entries: DepotJournalEntry[] }
      return data.entries
    },
    refetchInterval: 15_000,
  })
}

export function useAddDepotNote(depotProjectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: string) => {
      const r = await fetch(`${DEPOT_URL}/api/projects/${depotProjectId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body }),
      })
      return r.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['depot-journal', depotProjectId] }),
  })
}

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<{ projects: ProjectSummary[]; depot_reachable: boolean }>('/projects'),
  })
}

export function useProject(depotProjectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', depotProjectId],
    queryFn: () => api.get<ProjectDetail>(`/projects/${depotProjectId}`),
    enabled: !!depotProjectId,
  })
}

export function useUpdateTension(depotProjectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { priority?: string; due_date?: string | null }) =>
      api.put<Tension>(`/projects/${depotProjectId}/tension`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', depotProjectId] })
    },
  })
}

export function useProjectChat(depotProjectId: string) {
  return useMutation({
    mutationFn: (messages: ChatMessage[]) =>
      api.post<ChatResult>(`/projects/${depotProjectId}/chat`, { messages }),
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; ai_configured: boolean; depot_reachable: boolean }>('/health'),
    staleTime: 60_000,
  })
}
