import { useEffect, useRef } from 'react'
import type { AcquisitionLine, SupplyStage } from '../api/types'
import { shortDate } from '../lib/format'
import './AcquisitionTable.css'

const STEPS = ['Master', 'PR', 'PO', 'Conf.', 'Rec’d', 'Stock']
const STEP_TITLES = ['S4 material master', 'Purchase requisition', 'Purchase order', 'Supplier confirmed', 'Goods received', 'In stock']

/** How many of STEPS are complete for a stage, and whether the next one is a problem. */
function progress(stage: SupplyStage): { done: number; bad: boolean } {
  switch (stage) {
    case 'no_master':
      return { done: 0, bad: true }
    case 'no_pr':
      return { done: 1, bad: true }
    case 'pr_created':
      return { done: 1, bad: false }
    case 'pr_released':
      return { done: 2, bad: false }
    case 'po_placed':
      return { done: 3, bad: false }
    case 'po_confirmed':
      return { done: 4, bad: false }
    case 'in_inspection':
      return { done: 5, bad: false }
    case 'rejected':
      return { done: 5, bad: true }
    case 'in_stock':
      return { done: 6, bad: false }
    case 'in_house':
      return { done: 6, bad: false }
  }
}

/** Every component a build needs and how far S4 has got supplying it: master, PR, PO, supplier
 * confirmation, receipt, stock. With `showProject`, lines from several projects are labeled. */
export default function AcquisitionTable({
  lines,
  showProject,
  focus,
}: {
  lines: (AcquisitionLine & { project_name?: string | null; rank?: number | null })[]
  showProject?: boolean
  /** A material number to highlight and scroll to (from an issue link). */
  focus?: string | null
}) {
  const focusRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    focusRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focus, lines.length])
  if (lines.length === 0) return <p className="page__empty">Nothing to show.</p>
  const sorted = [...lines].sort((a, b) => Number(a.consumed) - Number(b.consumed))
  return (
    <div className="card acq">
      <div className="acq__row acq__row--head">
        <span>Material</span>
        <span>For</span>
        <span className="acq__steps-head">
          {STEPS.map((s, i) => (
            <span key={s} title={STEP_TITLES[i]}>
              {s}
            </span>
          ))}
        </span>
        <span>Status</span>
        <span>Needed</span>
        <span>Ready</span>
      </div>
      {sorted.map((l, i) => {
        const { done, bad } = progress(l.stage)
        const late = (l.late_days ?? 0) > 0 || l.past_due
        return (
          <div
            key={`${l.order_number}-${l.material_number}-${i}`}
            ref={focus && l.material_number === focus ? focusRef : undefined}
            className={`acq__row${l.consumed ? ' acq__row--consumed' : ''}${focus && l.material_number === focus ? ' acq__row--focus' : ''}`}
          >
            <span className="acq__material">
              <span className="mono">{l.material_number}</span>
              <span className="acq__desc">
                {l.description ?? '—'} · {l.quantity} {l.unit}
              </span>
            </span>
            <span className="acq__for mono">
              {showProject && (
                <span className="acq__project">
                  #{l.rank} {l.project_name}
                  <br />
                </span>
              )}
              {l.order_number}
              <br />
              op {l.operation_seq}
            </span>
            <span className="acq__steps">
              {l.stage === 'in_house' ? (
                <span className="acq__inhouse">Made in-house on {l.ref}</span>
              ) : l.ref === 'plant stock' ? (
                <span className="acq__inhouse acq__plant">From plant stock</span>
              ) : (
                STEPS.map((s, idx) => (
                  <span
                    key={s}
                    title={STEP_TITLES[idx]}
                    className={`acq__dot${idx < done ? ' acq__dot--done' : ''}${idx === done && bad ? ' acq__dot--bad' : ''}${idx === done && !bad ? ' acq__dot--next' : ''}`}
                  />
                ))
              )}
            </span>
            <span className="acq__status">
              <span className={bad ? 'acq__stage--bad' : ''}>{l.stage_label}</span>
              {l.po && (
                <span className="acq__sub">
                  PO {l.po.po_number} · {l.po.supplier}
                  {!l.po.confirmed_date && !l.po.gr_date && ' · supplier hasn’t confirmed'}
                </span>
              )}
              {!l.po && l.pr && (
                <span className="acq__sub">
                  PR {l.pr.pr_number} · {l.pr.release_status === 'released' ? 'released, no PO yet' : 'not released'}
                </span>
              )}
              {!l.master_exists && <span className="acq__sub">On the engineering BOM only. Create the S4 master.</span>}
              {l.consumed && <span className="acq__sub">Consumed</span>}
            </span>
            <span className="acq__date">{l.consumed ? '—' : shortDate(l.need_date)}</span>
            <span className="acq__date">
              {l.consumed ? '—' : l.ready_date ? shortDate(l.ready_date) : <span className="acq__stage--bad">No date</span>}
              {!l.consumed && late && (
                <span className="acq__late">{l.past_due ? 'past due' : `${l.late_days} wd late`}</span>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}

