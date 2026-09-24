import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useConstraints, useCreateProposal, useDecideProposal, useProjects, useProposals, useScenario } from '../api/hooks'
import type { Constraints, Lever, LeverType, Proposal, QueueItem, ScenarioResult, WorkCenterRow } from '../api/types'
import '../components/IssueBadges.css'

type MaterialBlocker = Constraints['material_blockers'][number]
import AiPanel from '../components/AiPanel'
import { OpStateChip, SlackValue, StatusChip } from '../components/Status'
import { duration, shortDate } from '../lib/format'
import { usePersona } from '../lib/persona'
import { useScope } from '../lib/scope'
import './ConstraintsPage.css'

const LEVER_LABEL: Record<LeverType, string> = {
  add_hours: 'Overtime / extra shift',
  move_labor: 'Move labor',
  add_equipment: 'Add equipment',
  outsource: 'Outsource an op',
  expedite_material: 'Expedite material',
}

export default function ConstraintsPage() {
  const { data, isLoading } = useConstraints()
  const { data: projects } = useProjects()
  const scenario = useScenario()
  const [levers, setLevers] = useState<Lever[]>([])
  const [panel, setPanel] = useState<'whatif' | 'ai' | null>(null)
  const [tab, setTab] = useState<'work' | 'material'>('work')
  const result = levers.length > 0 ? scenario.data : undefined
  const wcRows = result?.work_centers ?? data?.work_centers ?? []

  function run(next: Lever[]) {
    setLevers(next)
    if (next.length > 0 && next.every(complete)) scenario.mutate(next)
  }

  function expedite(b: MaterialBlocker) {
    setPanel('whatif')
    run([
      ...levers,
      { type: 'expedite_material', material_number: b.material_number, project_id: b.depot_project_id, ready_date: b.need_date ?? undefined },
    ])
    window.scrollTo?.({ top: 0 })
    document.querySelector('.page__content')?.scrollIntoView({ behavior: 'smooth' })
  }

  const bottleneck = data?.work_centers.find((w) => w.is_bottleneck)
  const trouble = projects?.projects.filter((p) => p.forecast.status === 'late' || p.forecast.status === 'blocked') ?? []

  return (
    <div className="page__content">
      <h1>Constraints</h1>
      <p className="page__sub">
        What's holding the work up, capacity or material, and what it would take to clear it: more hours, moving people,
        new equipment, outsourcing, or expediting a part.
      </p>

      {isLoading || !data ? (
        <p className="page__empty">Loading…</p>
      ) : (
        <>
          <div className="kpis">
            <button className="kpi card" onClick={() => setTab('work')}>
              <span className="kpi__label">Bottleneck</span>
              <span className="kpi__value">{bottleneck?.code ?? '—'}</span>
              <span className="kpi__note">
                {bottleneck
                  ? `${bottleneck.wip_days} days of work in front of it${bottleneck.extra_people_to_clear_in_week > 0 ? ` · +${bottleneck.extra_people_to_clear_in_week} people to clear in a week` : ''}`
                  : 'Nothing queued'}
              </span>
            </button>
            <button className="kpi card" onClick={() => setTab('material')}>
              <span className="kpi__label">Waiting on material</span>
              <span className={`kpi__value${data.material_blockers.length ? ' kpi__value--warn' : ''}`}>
                {data.material_blockers.length}
              </span>
              <span className="kpi__note">parts missing, undated or late for the step that needs them</span>
            </button>
            <Link className="kpi card" to="/triage">
              <span className="kpi__label">Late or blocked</span>
              <span className={`kpi__value${trouble.length ? ' kpi__value--bad' : ''}`}>
                {trouble.length} of {projects?.projects.length ?? 0}
              </span>
              <span className="kpi__note">projects at today's ranking and capacity</span>
            </Link>
          </div>

          <div className="adv-bar card">
            <span className="adv-bar__lead">
              {result ? (
                <>
                  🧪 <strong>{levers.length} lever{levers.length === 1 ? '' : 's'}</strong>: late days{' '}
                  {result.summary.late_days_before} → <strong>{result.summary.late_days_after}</strong>
                  {result.summary.recovered.length > 0 && (
                    <span className="to-good"> · {result.summary.recovered.length} back on time</span>
                  )}
                  <button className="adv-bar__try" onClick={() => run([])}>
                    Clear
                  </button>
                </>
              ) : (
                'Try a change and see every project’s finish date move before anyone commits to it.'
              )}
            </span>
            <span className="adv-bar__tabs">
              <button className={panel === 'whatif' ? 'adv-bar__tab--on' : ''} onClick={() => setPanel(panel === 'whatif' ? null : 'whatif')}>
                🧪 What if…
              </button>
              <button className={panel === 'ai' ? 'adv-bar__tab--on' : ''} onClick={() => setPanel(panel === 'ai' ? null : 'ai')}>
                ✨ Ask AI
              </button>
            </span>
          </div>

          {panel === 'whatif' && (
            <div className="adv-panel">
              <Sandbox
                levers={levers}
                workCenters={data.work_centers}
                blockers={data.material_blockers}
                onChange={run}
                running={scenario.isPending}
                error={scenario.error?.message}
              />
              {result && <ScenarioOutcome result={result} levers={levers} />}
              <SavedScenarios onLoad={run} />
            </div>
          )}
          {panel === 'ai' && (
            <div className="adv-panel">
              <AiPanel
                kind="constraint"
                placeholder="e.g. Get Nacelle and Bracket on time without overtime past the end of the month."
              />
            </div>
          )}

          <div className="cs-tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'work'} className={tab === 'work' ? 'cs-tab--on' : ''} onClick={() => setTab('work')}>
              Work centers
            </button>
            <button
              role="tab"
              aria-selected={tab === 'material'}
              className={tab === 'material' ? 'cs-tab--on' : ''}
              onClick={() => setTab('material')}
            >
              Waiting on material <span className="cs-tab__count">{data.material_blockers.length}</span>
            </button>
          </div>

          {tab === 'work' ? (
            <div className="card wc-table">
              <div className="wc-row wc-row--head">
                <span>Work center</span>
                <span>Queue</span>
                <span>Days of work waiting</span>
                <span>Oldest in queue</span>
                <span title="Median time from arrival to start, from past S4 confirmations">Typical wait</span>
                <span title="People (one 8-hour shift each) on top of today's capacity to clear everything waiting or running here within a week">
                  To clear in a week
                </span>
                <span>{result ? 'Scenario load' : 'Forecast load'}, next 10 working days</span>
              </div>
              {wcRows.map((wc) => (
                <WorkCenterLine key={wc.code} wc={wc} maxDays={Math.max(...wcRows.map((w) => w.wip_days), 1)} />
              ))}
            </div>
          ) : data.material_blockers.length === 0 ? (
            <p className="page__empty">Nothing is waiting on material.</p>
          ) : (
            <div className="card mb-table">
              {data.material_blockers.map((b, i) => (
                <MaterialBlockerRow key={`${b.order_number}-${b.material_number}-${i}`} b={b} onExpedite={() => expedite(b)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function complete(lv: Lever): boolean {
  switch (lv.type) {
    case 'add_hours':
    case 'add_equipment':
      return !!lv.work_center && !!lv.hours_per_day
    case 'move_labor':
      return !!lv.from_work_center && !!lv.to_work_center && !!lv.hours_per_day && lv.from_work_center !== lv.to_work_center
    case 'outsource':
      return !!lv.order_number && !!lv.seq && !!lv.turnaround_days
    case 'expedite_material':
      return !!lv.material_number && !!lv.ready_date
  }
}

function describe(lv: Lever): string {
  switch (lv.type) {
    case 'add_hours':
      return `+${lv.hours_per_day} h/day at ${lv.work_center}${lv.start_date ? ` from ${shortDate(lv.start_date)}` : ''}${lv.end_date ? ` to ${shortDate(lv.end_date)}` : ''}`
    case 'add_equipment':
      return `New equipment at ${lv.work_center}: +${lv.hours_per_day} h/day${lv.start_date ? ` from ${shortDate(lv.start_date)}` : ''}`
    case 'move_labor':
      return `Move ${lv.hours_per_day} h/day ${lv.from_work_center} → ${lv.to_work_center}`
    case 'outsource':
      return `Outsource ${lv.order_number} op ${lv.seq}, ${lv.turnaround_days} working days`
    case 'expedite_material':
      return `${lv.material_number} lands by ${shortDate(lv.ready_date)}`
  }
}

function Sandbox({
  levers,
  workCenters,
  blockers,
  onChange,
  running,
  error,
}: {
  levers: Lever[]
  workCenters: WorkCenterRow[]
  blockers: MaterialBlocker[]
  onChange: (levers: Lever[]) => void
  running: boolean
  error?: string
}) {
  const queued: QueueItem[] = workCenters.flatMap((w) => w.queue)
  const bottleneck = workCenters.find((w) => w.is_bottleneck)?.code ?? workCenters[0]?.code
  const set = (i: number, patch: Partial<Lever>) => onChange(levers.map((lv, j) => (j === i ? { ...lv, ...patch } : lv)))

  function add(type: LeverType) {
    const b0 = blockers[0]
    const base: Lever =
      type === 'move_labor'
        ? { type, from_work_center: '', to_work_center: bottleneck, hours_per_day: 8 }
        : type === 'outsource'
          ? { type, order_number: queued[0]?.order_number, seq: queued[0]?.seq, turnaround_days: 5 }
          : type === 'expedite_material'
            ? { type, material_number: b0?.material_number, project_id: b0?.depot_project_id, ready_date: b0?.need_date ?? undefined }
            : { type, work_center: bottleneck, hours_per_day: 8 }
    onChange([...levers, base])
  }

  const wcSelect = (value: string | undefined, onPick: (v: string) => void, blank = false) => (
    <select className="input" value={value ?? ''} onChange={(e) => onPick(e.target.value)}>
      {blank && <option value="">Pick…</option>}
      {workCenters.map((w) => (
        <option key={w.code} value={w.code}>
          {w.code} · {w.description}
        </option>
      ))}
    </select>
  )

  return (
    <div className="sb card">
      <div className="sb__add">
        <span className="sb__add-label">Add a lever:</span>
        {(Object.keys(LEVER_LABEL) as LeverType[]).map((t) => (
          <button
            key={t}
            className="mt-btn mt-btn--ghost"
            onClick={() => add(t)}
            disabled={(t === 'outsource' && queued.length === 0) || (t === 'expedite_material' && blockers.length === 0)}
          >
            + {LEVER_LABEL[t]}
          </button>
        ))}
      </div>
      {levers.length === 0 && (
        <p className="page__empty sb__empty">No levers yet. Add one to see every project's finish date move.</p>
      )}
      {levers.map((lv, i) => (
        <div key={i} className="sb__lever">
          <span className="sb__type">{LEVER_LABEL[lv.type]}</span>
          {(lv.type === 'add_hours' || lv.type === 'add_equipment') && (
            <>
              {wcSelect(lv.work_center, (v) => set(i, { work_center: v }))}
              <NumberField label="h/day" value={lv.hours_per_day} onChange={(v) => set(i, { hours_per_day: v })} />
            </>
          )}
          {lv.type === 'move_labor' && (
            <>
              <span className="sb__word">from</span>
              {wcSelect(lv.from_work_center, (v) => set(i, { from_work_center: v }), true)}
              <span className="sb__word">to</span>
              {wcSelect(lv.to_work_center, (v) => set(i, { to_work_center: v }))}
              <NumberField label="h/day" value={lv.hours_per_day} onChange={(v) => set(i, { hours_per_day: v })} />
            </>
          )}
          {lv.type === 'outsource' && (
            <>
              <select
                className="input"
                value={`${lv.order_number}/${lv.seq}`}
                onChange={(e) => {
                  const [order_number, seq] = e.target.value.split('/')
                  set(i, { order_number, seq: Number(seq) })
                }}
              >
                {queued.map((q) => (
                  <option key={`${q.order_number}/${q.seq}`} value={`${q.order_number}/${q.seq}`}>
                    {q.order_number} op {q.seq} {q.description} ({q.project_name})
                  </option>
                ))}
              </select>
              <NumberField label="working days" value={lv.turnaround_days} onChange={(v) => set(i, { turnaround_days: v })} />
              <span className="sb__input-note" title="Vendor turnaround isn't in S4. This number is yours.">
                your input
              </span>
            </>
          )}
          {lv.type === 'expedite_material' && (
            <>
              <select
                className="input"
                value={`${lv.project_id}|${lv.material_number}`}
                onChange={(e) => {
                  const [project_id, material_number] = e.target.value.split('|')
                  set(i, { project_id, material_number })
                }}
              >
                {blockers.map((b) => (
                  <option key={`${b.depot_project_id}|${b.material_number}`} value={`${b.depot_project_id}|${b.material_number}`}>
                    {b.material_number} {b.description} ({b.project_name})
                  </option>
                ))}
              </select>
              <DateField label="lands by" value={lv.ready_date} onChange={(v) => set(i, { ready_date: v })} />
              <span className="sb__input-note" title="An expedited date isn't in S4 until the supplier confirms it. This date is yours.">
                your input
              </span>
            </>
          )}
          {lv.type !== 'outsource' && lv.type !== 'expedite_material' && (
            <>
              <DateField label="from" value={lv.start_date} onChange={(v) => set(i, { start_date: v })} />
              {lv.type !== 'add_equipment' && (
                <DateField label="to" value={lv.end_date} onChange={(v) => set(i, { end_date: v })} />
              )}
            </>
          )}
          <button className="sb__remove" aria-label="Remove lever" onClick={() => onChange(levers.filter((_, j) => j !== i))}>
            ✕
          </button>
        </div>
      ))}
      {running && <p className="basis-note">Running the forecast…</p>}
      {error && <p className="to-error">{error}</p>}
    </div>
  )
}

function NumberField({ label, value, onChange }: { label: string; value?: number; onChange: (v: number) => void }) {
  return (
    <label className="sb__field">
      <input
        className="input sb__num"
        type="number"
        min={0}
        step={1}
        value={value ?? ''}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span>{label}</span>
    </label>
  )
}

function DateField({ label, value, onChange }: { label: string; value?: string; onChange: (v: string | undefined) => void }) {
  return (
    <label className="sb__field">
      <span>{label}</span>
      <input className="input" type="date" value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)} />
    </label>
  )
}

function ScenarioOutcome({ result, levers }: { result: ScenarioResult; levers: Lever[] }) {
  const s = result.summary
  const [title, setTitle] = useState('')
  const { persona } = usePersona()
  const save = useCreateProposal()
  const nameOf = (id: string) => result.projects.find((p) => p.depot_project_id === id)?.name ?? 'Project'

  return (
    <div className="so card">
      <p className="so__summary">
        Late days {s.late_days_before} → <strong>{s.late_days_after}</strong>
        {s.recovered.length > 0 && <span className="to-good"> · back on time: {s.recovered.map(nameOf).join(', ')}</span>}
        {s.newly_late.length > 0 && <span className="to-bad"> · goes late: {s.newly_late.map(nameOf).join(', ')}</span>}
      </p>
      <div className="so__rows">
        {result.projects.map((r) => (
          <div key={r.depot_project_id} className="so__row">
            <span>
              #{r.current.rank} {r.name}
            </span>
            <span>
              {shortDate(r.current.projected_finish)} → <strong>{shortDate(r.proposed.projected_finish)}</strong>
              {r.finish_delta_days ? (
                <span className={r.finish_delta_days > 0 ? 'to-bad' : 'to-good'}>
                  {' '}
                  ({r.finish_delta_days > 0 ? '+' : ''}
                  {r.finish_delta_days}d)
                </span>
              ) : null}
            </span>
            <SlackValue days={r.proposed.slack_days} />
            <StatusChip status={r.proposed.status} />
          </div>
        ))}
      </div>
      <div className="so__save">
        <input className="input" placeholder="Name this scenario" value={title} onChange={(e) => setTitle(e.target.value)} />
        <button
          className="mt-btn mt-btn--ghost"
          disabled={!title.trim() || !persona || save.isPending}
          onClick={() =>
            save.mutate(
              { kind: 'capacity', source: 'person', title: title.trim(), created_by: persona?.name, levers, rationale: levers.map(describe).join('; ') },
              { onSuccess: () => setTitle('') },
            )
          }
        >
          Save as proposal
        </button>
      </div>
      {save.isSuccess && <p className="basis-note">Saved below. Leadership can accept or dismiss it there.</p>}
    </div>
  )
}

function SavedScenarios({ onLoad }: { onLoad: (levers: Lever[]) => void }) {
  const { data } = useProposals('capacity')
  const decide = useDecideProposal()
  const { persona } = usePersona()
  const proposals = data?.proposals ?? []
  if (proposals.length === 0) return null
  return (
    <div className="ss">
      <h3 className="ss__h">Capacity proposals</h3>
      {proposals.map((p: Proposal) => (
        <div key={p.id} className={`ss__item card ss__item--${p.status}`}>
          <div className="ss__head">
            <strong>{p.title}</strong>
            <span className={`src-tag src-tag--${p.source}`}>{p.source === 'ai' ? 'AI' : p.created_by ?? 'person'}</span>
            <span className="ss__status">{p.status}</span>
          </div>
          <div className="ss__levers">{(p.levers ?? []).map(describe).join(' · ')}</div>
          <div className="ss__actions">
            <button className="mt-btn mt-btn--ghost" onClick={() => onLoad(p.levers ?? [])}>
              Load
            </button>
            {p.status === 'open' ? (
              <>
                <button
                  className="mt-btn mt-btn--primary"
                  disabled={!persona}
                  onClick={() => persona && decide.mutate({ id: p.id, decision: 'accept', name: persona.name, personId: persona.id })}
                >
                  Accept
                </button>
                <button
                  className="mt-btn mt-btn--ghost"
                  disabled={!persona}
                  onClick={() => persona && decide.mutate({ id: p.id, decision: 'dismiss', name: persona.name, personId: persona.id })}
                >
                  Dismiss
                </button>
                <span className="basis-note">as {persona?.name}. Accepting logs it to each affected project's Journal.</span>
              </>
            ) : (
              <span className="basis-note">
                {p.status} by {p.decided_by}
                {p.status === 'accepted' && '. The capacity change itself happens in S4.'}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function MaterialBlockerRow({ b, onExpedite }: { b: MaterialBlocker; onExpedite: () => void }) {
  const { setProjectId } = useScope()
  return (
    <div className="mb-row">
      <span className="mb-rank">#{b.rank}</span>
      <span className="mb-project">
        <Link to="/material" onClick={() => setProjectId(b.depot_project_id)}>
          {b.project_name ?? 'Project'}
        </Link>
        <span className="muted mono">
          {b.order_number} op {b.operation_seq}
        </span>
      </span>
      <span>
        <span className="mono">{b.material_number}</span> {b.description}
      </span>
      <span className="mb-stage">
        {b.stage_label}
        <span className="mb-fix">
          <span className="ib__owner">{b.owner}</span> {b.action}
        </span>
      </span>
      <span className="mb-when">
        {b.ready_date ? (
          <>
            ready {shortDate(b.ready_date)}
            {b.past_due ? (
              <span className="mb-late"> · past due</span>
            ) : b.late_days ? (
              <span className="mb-late"> · {b.late_days} wd late</span>
            ) : null}
          </>
        ) : (
          <span className="mb-late">no date from S4</span>
        )}
        <button className="mb-whatif" onClick={onExpedite} title="Try it in the what-if sandbox">
          What if it landed by {shortDate(b.need_date)}?
        </button>
      </span>
    </div>
  )
}

function WorkCenterLine({ wc, maxDays }: { wc: WorkCenterRow; maxDays: number }) {
  const [open, setOpen] = useState(false)
  const { setProjectId } = useScope()
  const items = [...wc.in_process, ...wc.queue]
  const hot = wc.queue_days >= 2
  return (
    <>
      <button
        className={`wc-row wc-row--btn${open ? ' wc-row--open' : ''}${wc.is_bottleneck ? ' wc-row--bottleneck' : ''}`}
        onClick={() => setOpen(!open)}
        disabled={!items.length}
      >
        <span className="wc-name">
          <span className="mono">
            {wc.code}
            {wc.is_bottleneck && <span className="wc-tag">bottleneck</span>}
          </span>
          <span className="muted">
            {wc.description} · {wc.capacity_hours_per_day} h/day
          </span>
        </span>
        <span>
          <strong>{wc.queue_count}</strong> waiting
          {wc.in_process.length > 0 && <span className="muted"> · {wc.in_process.length} running</span>}
        </span>
        <span className="wc-bar">
          <span className="wc-bar__track">
            <span className="wc-bar__queue" style={{ width: `${(wc.queue_days / maxDays) * 100}%` }} />
            <span className="wc-bar__wip" style={{ width: `${((wc.wip_days - wc.queue_days) / maxDays) * 100}%` }} />
          </span>
          <span className={hot ? 'wc-hot' : ''}>
            {wc.queue_days}d<span className="muted"> ({wc.queued_hours} h)</span>
          </span>
        </span>
        <span>{wc.queue_count ? duration(wc.oldest_dwell_hours) : '—'}</span>
        <span>
          {duration(wc.median_wait_hours)}
          {wc.history_count > 0 && <span className="muted"> · n={wc.history_count}</span>}
        </span>
        <span>
          {wc.extra_people_to_clear_in_week > 0 ? (
            <strong className="wc-hot">+{wc.extra_people_to_clear_in_week} people</strong>
          ) : (
            <span className="muted">—</span>
          )}
        </span>
        <span className="wc-spark" title={`${Math.round(wc.utilization_next_10 * 100)}% of capacity booked`}>
          {wc.load_next_10.map((h, i) => {
            const cap = wc.capacity_next_10[i] || wc.capacity_hours_per_day
            return (
              <span
                key={i}
                className={`wc-spark__bar${h >= cap - 0.01 && h > 0 ? ' wc-spark__bar--full' : ''}`}
                style={{ height: `${Math.max((h / Math.max(cap, 1)) * 100, h > 0 ? 8 : 2)}%` }}
              />
            )
          })}
          <span className="wc-spark__pct">{Math.round(wc.utilization_next_10 * 100)}%</span>
        </span>
      </button>
      {open && (
        <div className="wc-queue">
          {items.map((q) => (
            <div key={`${q.order_number}-${q.seq}`} className="wc-queue__item">
              <span className="mb-rank">#{q.rank ?? '–'}</span>
              <Link to="/routing" onClick={() => setProjectId(q.depot_project_id)}>
                {q.project_name ?? 'Project'}
              </Link>
              <span className="mono">
                {q.order_number} op {q.seq}
              </span>
              <span>{q.description}</span>
              <OpStateChip state={q.state} />
              <span>{duration(q.dwell_hours)} here</span>
              <span className="muted">{q.remaining_hours} std h</span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
