import { Link } from 'react-router-dom'
import type { ProjectRow } from '../api/types'
import { shortDate } from '../lib/format'
import { ImpactReason, SlackValue, StatusChip } from './Status'
import './ProjectStrip.css'

/** The one-line Impact summary shown at the top of a project-scoped page. */
export default function ProjectStrip({ row }: { row: ProjectRow }) {
  const f = row.forecast
  return (
    <div className="pd__impact card">
      <div className="pd__fact pd__fact--name">
        <div className="pd__fact-label">Project</div>
        <div className="pd__fact-value">
          {row.name ?? 'Unknown project'} <StatusChip status={f.status} />
        </div>
      </div>
      <Fact label="Rank" value={<Link to="/triage">#{f.rank}</Link>} />
      <Fact label="Need by" value={shortDate(f.need_by)} />
      <Fact label="Forecast finish" value={f.projected_finish ? shortDate(f.projected_finish) : 'Can’t forecast'} />
      <Fact label="Slack" value={<SlackValue days={f.slack_days} />} />
      <div className="pd__impact-why">
        <div className="pd__fact-label">Impact</div>
        <ImpactReason forecast={f} />
        <div className="basis-note">S4 standard hours, shared work centers loaded in rank order, Mon–Fri.</div>
      </div>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="pd__fact">
      <div className="pd__fact-label">{label}</div>
      <div className="pd__fact-value">{value}</div>
    </div>
  )
}
