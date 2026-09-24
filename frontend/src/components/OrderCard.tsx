import type { ClearToBuildStatus, Operation, ProductionOrder } from '../api/types'
import { DESIGNATOR_LABEL } from '../api/types'
import { duration, shortDate, shortDateTime } from '../lib/format'
import { OpStateChip } from './Status'
import './RoutingTree.css'

export const CTB_LABEL: Record<ClearToBuildStatus, string> = {
  clear: 'Clear to build',
  running: 'Running',
  waiting_material: 'Waiting on material',
  held: 'On hold',
  not_released: 'Not released',
  complete: 'Complete',
}

export function OrderCard({ order }: { order: ProductionOrder }) {
  const ctb = order.clear_to_build
  return (
    <div className="card order">
      <div className="order__head">
        <div>
          <span className="mono order__num">{order.order_number}</span>{' '}
          <strong>{order.description ?? order.material_number}</strong>
          <span className="muted">
            {' '}
            · {order.material_number} · qty {order.quantity}
          </span>
        </div>
        <span className={`chip ctb--${ctb.status}`}>{CTB_LABEL[ctb.status]}</span>
      </div>
      <div className="order__ctb">{ctb.reason}</div>

      <ol className="track">
        {order.operations.map((op) => (
          <TrackStep key={op.id} op={op} here={op.seq === order.current_seq} />
        ))}
      </ol>

      <details className="order__history">
        <summary>Operation history &amp; forecast</summary>
        <table className="optable">
          <thead>
            <tr>
              <th>Op</th>
              <th>Work center</th>
              <th>Arrived</th>
              <th>Started</th>
              <th>Finished</th>
              <th>Queue wait</th>
              <th>Dwell</th>
              <th>Yield / scrap / rework</th>
              <th>Std hrs</th>
              <th>Forecast</th>
            </tr>
          </thead>
          <tbody>
            {order.operations.map((op) => (
              <tr key={op.id} className={op.seq === order.current_seq ? 'optable__here' : ''}>
                <td>
                  {op.seq} {op.description}
                </td>
                <td className="mono">{op.work_center}</td>
                <td>{shortDateTime(op.arrived_at)}</td>
                <td>{shortDateTime(op.started_at)}</td>
                <td>{shortDateTime(op.finished_at)}</td>
                <td>{duration(op.wait_hours)}</td>
                <td>{duration(op.dwell_hours)}</td>
                <td>
                  {op.yield_qty} / {op.scrap_qty} / {op.rework_qty}
                </td>
                <td>{op.standard_hours}</td>
                <td>
                  {op.forecast.blocked
                    ? 'Blocked'
                    : op.forecast.start_date
                      ? `${shortDate(op.forecast.start_date)} – ${shortDate(op.forecast.finish_date)}`
                      : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

function TrackStep({ op, here }: { op: Operation; here: boolean }) {
  const waitingMaterial = op.components.filter((c) => !c.available_now)
  const showMaterial = op.state !== 'done' && waitingMaterial.length > 0
  return (
    <li className={`track__step track__step--${op.state}${here ? ' track__step--here' : ''}`}>
      {here && <span className="track__here">▶ here</span>}
      <div className="track__seq">
        {op.seq} · <span className="mono">{op.work_center}</span>
      </div>
      <div className="track__desc">{op.description}</div>
      <OpStateChip state={op.state} />
      {(op.state === 'queued' || op.state === 'in_process' || op.state === 'on_hold') && (
        <div className="track__dwell">
          {duration(op.dwell_hours)} here
          {op.state === 'in_process' && op.wait_hours != null && (
            <span className="muted"> · waited {duration(op.wait_hours)}</span>
          )}
        </div>
      )}
      {op.state === 'done' && <div className="track__dwell muted">{duration(op.dwell_hours)}</div>}
      {op.quality.map((q) => (
        <span
          key={q.id}
          className={`chip ${q.open ? 'chip--quality' : 'chip--quality-closed'}`}
          title={`QN ${q.notification_number}: ${q.description}`}
        >
          {DESIGNATOR_LABEL[q.designator]}
          {q.quantity ? ` ×${q.quantity}` : ''}
        </span>
      ))}
      {showMaterial && (
        <div className="track__material" title={waitingMaterial.map((c) => `${c.material_number}: ${c.stage_label}`).join('\n')}>
          ⏳ {waitingMaterial.map((c) => c.material_number).join(', ')}
        </div>
      )}
      {op.state !== 'done' && op.forecast.start_date && !op.forecast.blocked && (
        <div className="track__fc">
          fc {shortDate(op.forecast.start_date)}
          {(op.forecast.capacity_wait_days ?? 0) >= 0.5 && (
            <span className="track__wait"> · {op.forecast.capacity_wait_days}d queue</span>
          )}
        </div>
      )}
    </li>
  )
}
