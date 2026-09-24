export type ForecastStatus = 'on_track' | 'at_risk' | 'late' | 'blocked' | 'no_need_by' | 'no_orders'

export const STATUS_LABEL: Record<ForecastStatus, string> = {
  on_track: 'On track',
  at_risk: 'At risk',
  late: 'Late',
  blocked: 'Blocked',
  no_need_by: 'No need-by',
  no_orders: 'No orders',
}

export interface Blocker {
  kind: 'material' | 'hold'
  reason: string
  material?: string
  order?: string
  seq?: number
}

export interface Driver {
  kind: 'capacity' | 'material'
  key: string
  days: number
}

export interface ProjectForecast {
  rank: number
  need_by: string | null
  projected_finish: string | null
  slack_days: number | null
  status: ForecastStatus
  blocker: Blocker | null
  drivers: Driver[]
}

export interface Location {
  order_number: string
  seq: number | null
  work_center: string | null
  state: OpState | null
  dwell_hours: number | null
}

export interface ProjectSize {
  parts_left: number
  units_left: number
  ops_left: number
  std_hours_left: number
  bottleneck: string | null
  bottleneck_hours_left: number
}

/** One row on the Triage board / project list. */
export interface ProjectRow {
  depot_project_id: string
  name: string | null
  rank: number
  forecast: ProjectForecast
  size: ProjectSize
  orders_active: number
  orders_clear: number
  orders_waiting_material: number
  orders_held: number
  material_issues: number
  open_quality: number
  open_hot_flags: number
  locations: Location[]
  issues: Issue[]
}

/** One problem on a project, with who fixes it and where in MARTI to see it. */
export interface Issue {
  kind: 'short' | 'held' | 'quality' | 'flag'
  title: string
  detail: string
  owner: string
  action: string
  order_number: string | null
  material_number: string | null
  link: 'material' | 'routing' | 'hot-flags'
  focus: string | null
}

export interface DepotPerson {
  id: string
  name: string
  title: string | null
  is_admin: boolean
}

export type SupplyStage =
  | 'no_master'
  | 'no_pr'
  | 'pr_created'
  | 'pr_released'
  | 'po_placed'
  | 'po_confirmed'
  | 'in_inspection'
  | 'rejected'
  | 'in_stock'
  | 'in_house'

export interface PurchaseOrder {
  po_number: string
  pr_number: string | null
  supplier: string | null
  quantity: number
  created_on: string
  requested_date: string
  confirmed_date: string | null
  gr_date: string | null
  inspection_status: string
}

export interface PurchaseRequisition {
  pr_number: string
  quantity: number
  release_status: 'not_released' | 'released'
  created_on: string
}

export interface AcquisitionLine {
  material_number: string
  description: string | null
  master_exists: boolean
  procurement_type: 'E' | 'F' | 'X' | null
  quantity: number
  unit: string
  order_number: string
  operation_seq: number
  consumed: boolean
  stage: SupplyStage
  stage_label: string
  ref: string | null
  pr: PurchaseRequisition | null
  po: PurchaseOrder | null
  confirmed: boolean
  past_due: boolean
  need_date: string | null
  ready_date: string | null
  late_days: number | null
}

export type OpState = 'done' | 'in_process' | 'queued' | 'on_hold' | 'not_arrived'

export const OP_STATE_LABEL: Record<OpState, string> = {
  done: 'Done',
  in_process: 'In process',
  queued: 'Queued',
  on_hold: 'On hold',
  not_arrived: 'Not arrived',
}

export type QualityDesignator = 'defect' | 'rework' | 'mrb_hold' | 'scrap'

export const DESIGNATOR_LABEL: Record<QualityDesignator, string> = {
  defect: 'Defect',
  rework: 'Rework',
  mrb_hold: 'MRB hold',
  scrap: 'Scrap',
}

export interface QualityNotification {
  id: string
  notification_number: string
  operation_seq: number
  designator: QualityDesignator
  description: string
  quantity: number | null
  created_at: string
  closed_at: string | null
  open: boolean
}

export interface OpComponent {
  material_number: string
  description: string | null
  quantity: number
  stage: SupplyStage
  stage_label: string
  ref: string | null
  available_now: boolean
  ready_date: string | null
}

export interface Operation {
  id: string
  seq: number
  description: string
  work_center: string
  state: OpState
  setup_hours: number
  run_hours_per_unit: number
  standard_hours: number
  arrived_at: string | null
  started_at: string | null
  finished_at: string | null
  dwell_hours: number | null
  wait_hours: number | null
  yield_qty: number
  scrap_qty: number
  rework_qty: number
  quality: QualityNotification[]
  components: OpComponent[]
  forecast: {
    start_date?: string
    finish_date?: string
    capacity_wait_days?: number
    material_wait_days?: number
    hours?: number
    blocked?: Blocker
  }
}

export type ClearToBuildStatus = 'clear' | 'running' | 'waiting_material' | 'held' | 'not_released' | 'complete'

export interface ProductionOrder {
  order_id: string
  forecast_finish_date: string | null
  forecast_blocked: boolean
  order_number: string
  material_number: string
  description: string | null
  quantity: number
  released_at: string | null
  current_seq: number | null
  clear_to_build: { status: ClearToBuildStatus; reason: string; missing?: string[] }
  operations: Operation[]
}

export type ProposalSource = 'engine' | 'ai' | 'person'

export interface PriorityChange {
  id: string
  changed_by: string
  reason: string
  source: ProposalSource
  proposal_id: string | null
  person_id: string | null
  before: string[]
  after: string[]
  changed_at: string
}

export interface HotFlag {
  id: string
  depot_project_id: string
  project_name?: string | null
  target_kind: 'material' | 'operation'
  target_key: string
  owner: string
  title: string
  detail: string
  status: 'open' | 'acknowledged' | 'resolved'
  raised_at: string
  acknowledged_by: string | null
  acknowledged_at: string | null
  resolved_at: string | null
  priority_change: PriorityChange | null
}

export interface TreeNode extends ProductionOrder {
  children: TreeNode[]
  critical: boolean
  rollup: {
    orders: number
    complete: number
    ops_done: number
    ops_total: number
    held: number
    waiting_material: number
    open_quality: number
  }
}

export interface RoutingProject extends ProjectRow {
  tree: TreeNode[]
}

/** An acquisition line with the project it belongs to (the cross-project M&A view). */
export interface ScopedAcquisitionLine extends AcquisitionLine {
  depot_project_id: string
  project_name: string | null
  rank: number | null
}

export interface TriageBoard {
  projects: ProjectRow[]
  history: PriorityChange[]
  bottleneck: string | null
  depot_reachable: boolean
  as_of: string
}

export interface ImpactSummary {
  newly_late: string[]
  recovered: string[]
  late_days_before: number
  late_days_after: number
}

export interface CutIn {
  depot_project_id: string
  name: string | null
  current_rank: number
  gain_days: number
  cost_days: number
  newly_late: string[]
  forecastable: boolean
  cheap: boolean
  ranking: string[]
}

export type LeverType = 'add_hours' | 'move_labor' | 'add_equipment' | 'outsource' | 'expedite_material'

export interface Lever {
  type: LeverType
  work_center?: string
  from_work_center?: string
  to_work_center?: string
  hours_per_day?: number
  start_date?: string
  end_date?: string
  order_number?: string
  seq?: number
  turnaround_days?: number
  material_number?: string
  project_id?: string
  ready_date?: string
}

export interface Proposal {
  id: string
  kind: 'rerank' | 'capacity'
  source: ProposalSource
  title: string
  rationale: string | null
  ranking: string[] | null
  levers: Lever[] | null
  status: 'open' | 'committed' | 'accepted' | 'dismissed'
  created_by: string | null
  created_at: string
  decided_by: string | null
  decided_at: string | null
}

/** A ranking suggestion: from MARTI's engine (no id) or a saved proposal (AI / person). */
export interface RankingSuggestion {
  id?: string
  source: ProposalSource
  title: string
  rationale: string | null
  ranking: string[]
  impact: PreviewRow[]
  summary: ImpactSummary
}

export interface Suggestions {
  cut_in: CutIn[]
  rankings: RankingSuggestion[]
  proposals: RankingSuggestion[]
}

export interface ScenarioResult {
  projects: PreviewRow[]
  summary: ImpactSummary
  work_centers: WorkCenterRow[]
}

export interface AiSuggestResponse {
  status: 'not_connected' | 'ok'
  message: string
  proposals: Proposal[]
}

export interface PreviewRow {
  depot_project_id: string
  name: string | null
  current: ProjectForecast
  proposed: ProjectForecast
  finish_delta_days: number | null
  rank_delta: number
}

export interface QueueItem {
  depot_project_id: string
  project_name: string | null
  rank: number | null
  order_number: string
  seq: number
  description: string
  state: OpState
  arrived_at: string | null
  dwell_hours: number | null
  remaining_hours: number
}

export interface WorkCenterRow {
  code: string
  description: string
  capacity_hours_per_day: number
  queue: QueueItem[]
  in_process: QueueItem[]
  queue_count: number
  queued_hours: number
  queue_days: number
  wip_days: number
  oldest_dwell_hours: number | null
  history_count: number
  median_wait_hours: number | null
  median_dwell_hours: number | null
  load_next_10: number[]
  capacity_next_10: number[]
  utilization_next_10: number
  wip_hours: number
  is_bottleneck: boolean
  extra_people_to_clear_in_week: number
}

export interface MaterialBlocker extends AcquisitionLine {
  depot_project_id: string
  project_name: string | null
  rank: number | null
  owner: string
  action: string
}

export interface Constraints {
  work_centers: WorkCenterRow[]
  material_blockers: MaterialBlocker[]
  bottleneck: string | null
  as_of: string
}
