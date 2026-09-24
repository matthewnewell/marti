import { Link } from 'react-router-dom'
import { useAcknowledgeFlag, useResolveFlag } from '../api/hooks'
import type { HotFlag } from '../api/types'
import { relativeAgo, shortDateTime } from '../lib/format'
import { usePersona } from '../lib/persona'
import './FlagCard.css'

/** One hot flag: what's blocking, who owns it, the re-rank that raised it, and the
 * acknowledge → resolve flow, credited to whoever MARTI's user menu says is viewing. */
export default function FlagCard({ flag, showProject }: { flag: HotFlag; showProject?: boolean }) {
  const { persona } = usePersona()
  const ack = useAcknowledgeFlag()
  const resolve = useResolveFlag()
  const change = flag.priority_change

  return (
    <div className={`flag-card card flag-card--${flag.status}`}>
      <div className="flag-card__top">
        <span className="flag-card__icon" aria-hidden="true">
          {flag.status === 'resolved' ? '✓' : '🔥'}
        </span>
        <div className="flag-card__main">
          <div className="flag-card__title">{flag.title}</div>
          <div className="flag-card__meta">
            {showProject && (
              <>
                <Link to={`/projects/${flag.depot_project_id}`}>{flag.project_name ?? 'Project'}</Link> ·{' '}
              </>
            )}
            Owner: <strong>{flag.owner}</strong> · raised {relativeAgo(flag.raised_at)}
          </div>
        </div>
        <span className={`chip flag-chip--${flag.status}`}>{flag.status}</span>
      </div>

      <p className="flag-card__detail">{flag.detail}</p>

      {change && (
        <p className="flag-card__why">
          Raised when <strong>{change.changed_by}</strong> re-ranked on {shortDateTime(change.changed_at)}: “
          {change.reason}”
        </p>
      )}

      {flag.status === 'open' && (
        <div className="flag-card__actions">
          <button
            className="mt-btn mt-btn--primary"
            disabled={!persona || ack.isPending}
            onClick={() => persona && ack.mutate({ id: flag.id, name: persona.name })}
          >
            Acknowledge as {persona?.name ?? '…'}
          </button>
        </div>
      )}
      {flag.status === 'acknowledged' && (
        <div className="flag-card__actions">
          <span className="flag-card__ack">
            Acknowledged by <strong>{flag.acknowledged_by}</strong> {relativeAgo(flag.acknowledged_at)}
          </span>
          <button className="mt-btn mt-btn--ghost" disabled={resolve.isPending} onClick={() => resolve.mutate(flag.id)}>
            Mark resolved
          </button>
        </div>
      )}
      {flag.status === 'resolved' && (
        <div className="flag-card__ack">
          {flag.acknowledged_by && <>Acknowledged by {flag.acknowledged_by} · </>}Resolved {relativeAgo(flag.resolved_at)}
        </div>
      )}
    </div>
  )
}
