import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  AiSuggestResponse,
  Constraints,
  DepotPerson,
  HotFlag,
  Lever,
  PreviewRow,
  ImpactSummary,
  ProjectRow,
  Proposal,
  ProposalSource,
  RoutingProject,
  ScenarioResult,
  ScopedAcquisitionLine,
  Suggestions,
  TriageBoard,
} from './types'

/** Every MARTI read is derived from the same data, so any write invalidates all of it. */
function useInvalidateAll() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries()
}

const scopeQuery = (projectId: string | null) => (projectId ? `?project_id=${projectId}` : '')

export function usePeople() {
  return useQuery({
    queryKey: ['people'],
    queryFn: () => api.get<{ people: DepotPerson[]; depot_reachable: boolean }>('/people'),
    staleTime: 60_000,
  })
}

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<{ projects: ProjectRow[]; depot_reachable: boolean; as_of: string }>('/projects'),
  })
}

export function useAcquisition(projectId: string | null) {
  return useQuery({
    queryKey: ['acquisition', projectId],
    queryFn: () => api.get<{ lines: ScopedAcquisitionLine[]; as_of: string }>(`/acquisition${scopeQuery(projectId)}`),
  })
}

export function useRouting(projectId: string | null) {
  return useQuery({
    queryKey: ['routing', projectId],
    queryFn: () => api.get<{ projects: RoutingProject[]; as_of: string }>(`/routing${scopeQuery(projectId)}`),
  })
}

export function useTriage() {
  return useQuery({
    queryKey: ['triage'],
    queryFn: () => api.get<TriageBoard>('/triage'),
  })
}

export function useSuggestions() {
  return useQuery({
    queryKey: ['triage', 'suggestions'],
    queryFn: () => api.get<Suggestions>('/triage/suggestions'),
  })
}

/** What-if Impact for a proposed ranking. Disabled while the order matches what's saved. */
export function usePreview(order: string[] | null) {
  return useQuery({
    queryKey: ['triage', 'preview', order],
    queryFn: () => api.post<{ projects: PreviewRow[]; summary: ImpactSummary }>('/triage/preview', { order }),
    enabled: !!order,
    placeholderData: keepPreviousData,
  })
}

export function useCommitRanking() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (data: {
      order: string[]
      changed_by: string
      reason: string
      source?: ProposalSource
      proposal_id?: string
      person_id?: string
    }) => api.post<TriageBoard & { hot_flags_raised: HotFlag[]; journal_posted: number }>('/triage/commit', data),
    onSuccess: invalidate,
  })
}

export function useSetNeedBy() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ projectId, needBy }: { projectId: string; needBy: string | null }) =>
      api.put<TriageBoard>(`/triage/${projectId}/need-by`, { need_by: needBy }),
    onSuccess: invalidate,
  })
}

export function useConstraints() {
  return useQuery({
    queryKey: ['constraints'],
    queryFn: () => api.get<Constraints>('/constraints'),
  })
}

export function useScenario() {
  return useMutation({
    mutationFn: (levers: Lever[]) => api.post<ScenarioResult>('/constraints/scenario', { levers }),
  })
}

export function useProposals(kind: 'rerank' | 'capacity') {
  return useQuery({
    queryKey: ['proposals', kind],
    queryFn: () => api.get<{ proposals: Proposal[] }>(`/proposals?kind=${kind}`),
  })
}

export function useCreateProposal() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (data: Partial<Proposal> & { kind: Proposal['kind']; title: string }) =>
      api.post<Proposal>('/proposals', data),
    onSuccess: invalidate,
  })
}

export function useDecideProposal() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({
      id,
      decision,
      name,
      personId,
    }: {
      id: string
      decision: 'accept' | 'dismiss'
      name: string
      personId?: string
    }) => api.post<Proposal & { journal_posted?: number }>(`/proposals/${id}/${decision}`, { name, person_id: personId }),
    onSuccess: invalidate,
  })
}

/** Ask the AI for proposals. A stub today: the backend answers "not_connected". */
export function useAiSuggest(kind: 'triage' | 'constraint') {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (goals: string) => api.post<AiSuggestResponse>(`/ai/${kind}-suggestions`, { goals }),
    onSuccess: invalidate,
  })
}

export function useHotFlags(status: 'active' | 'all') {
  return useQuery({
    queryKey: ['hot-flags', status],
    queryFn: () => api.get<{ hot_flags: HotFlag[] }>(`/hot-flags${status === 'active' ? '?status=active' : ''}`),
  })
}

export function useAcknowledgeFlag() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.post<HotFlag>(`/hot-flags/${id}/acknowledge`, { name }),
    onSuccess: invalidate,
  })
}

export function useResolveFlag() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (id: string) => api.post<HotFlag>(`/hot-flags/${id}/resolve`),
    onSuccess: invalidate,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; ai_configured: boolean; depot_reachable: boolean }>('/health'),
    staleTime: 60_000,
  })
}
