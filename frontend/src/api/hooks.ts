import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ProjectDetail, ProjectSummary, Tradeoff } from './types'

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
      api.put<Tradeoff>(`/projects/${depotProjectId}/tradeoff`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', depotProjectId] })
    },
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; ai_configured: boolean; depot_reachable: boolean }>('/health'),
    staleTime: 60_000,
  })
}
