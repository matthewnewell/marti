import type { ForecastStatus, OpState, ProjectForecast } from '../api/types'
import { OP_STATE_LABEL, STATUS_LABEL } from '../api/types'
import { slack } from '../lib/format'

export function StatusChip({ status }: { status: ForecastStatus }) {
  return <span className={`chip chip--${status}`}>{STATUS_LABEL[status]}</span>
}

export function OpStateChip({ state }: { state: OpState }) {
  return <span className={`chip chip--op-${state}`}>{OP_STATE_LABEL[state]}</span>
}

export function SlackValue({ days }: { days: number | null }) {
  const cls = days == null ? '' : days < 0 ? 'slack--late' : days < 5 ? 'slack--risk' : 'slack--ok'
  return <span className={`slack ${cls}`}>{slack(days)}</span>
}

/** One line saying why a project lands where it does. */
export function ImpactReason({ forecast }: { forecast: ProjectForecast }) {
  if (forecast.blocker) return <span className="impact-reason impact-reason--blocked">{forecast.blocker.reason}</span>
  if (forecast.drivers.length === 0) return <span className="impact-reason">No waiting: runs straight through</span>
  return (
    <span className="impact-reason">
      {forecast.drivers
        .slice(0, 2)
        .map((d) => (d.kind === 'capacity' ? `${d.days}d queued for ${d.key}` : `${d.days}d waiting on ${d.key}`))
        .join(' · ')}
    </span>
  )
}
