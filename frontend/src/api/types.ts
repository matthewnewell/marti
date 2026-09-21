export type Priority = 'high' | 'medium' | 'low'
export const PRIORITIES: Priority[] = ['high', 'medium', 'low']
export const PRIORITY_LABEL: Record<Priority, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export type AcquisitionStatus = 'open' | 'released' | 'received' | 'on_hold'
export type RoutingStatus = 'not_started' | 'in_process' | 'complete' | 'on_hold'

export interface Impact {
  flagged: boolean
  reason: string
  days_to_due?: number
}

export interface Tradeoff {
  id: string
  depot_project_id: string
  priority: Priority
  due_date: string | null
  created_at: string
  updated_at: string
  impact: Impact
}

export interface AcquisitionOrder {
  id: string
  material_id: string
  order_number: string
  status: AcquisitionStatus
  need_date: string | null
  promise_date: string | null
  created_at: string
}

export interface Routing {
  id: string
  material_id: string
  operation_seq: number
  operation_name: string
  work_center: string | null
  status: RoutingStatus
  created_at: string
}

export interface Material {
  id: string
  depot_project_id: string
  material_number: string
  description: string | null
  procurement_type: 'E' | 'F' | 'X'
  created_at: string
  acquisition_orders: AcquisitionOrder[]
  routings: Routing[]
}

/** One row in the manufacturing-project list — `GET /api/projects`. */
export interface ProjectSummary {
  depot_project_id: string
  name: string
  has_manufacturing: boolean | null
  manufacturing_source: 'depot' | 'material'
  tradeoff: Tradeoff | null
  acquisition_orders_open: number
  acquisition_orders_total: number
  routing_ops_open: number
  routing_ops_total: number
}

/** `GET /api/projects/<id>` — one project's full detail. */
export interface ProjectDetail {
  depot_project_id: string
  name: string
  has_manufacturing: boolean | null
  materials: Material[]
  tradeoff: Tradeoff | null
}
