import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useCommitRanking, usePreview, useSetNeedBy, useSuggestions, useTriage } from '../api/hooks'
import type { CutIn, HotFlag, PreviewRow, ProjectRow, ProposalSource, RankingSuggestion } from '../api/types'
import AiPanel from '../components/AiPanel'
import IssueBadges from '../components/IssueBadges'
import { ImpactReason, SlackValue, StatusChip } from '../components/Status'
import { shortDate, shortDateTime } from '../lib/format'
import { usePersona } from '../lib/persona'
import { useScope } from '../lib/scope'
import './TriagePage.css'

function move<T>(list: T[], from: number, to: number): T[] {
  const next = [...list]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

const SOURCE_LABEL: Record<ProposalSource, string> = {
  engine: 'MARTI engine',
  ai: 'AI',
  person: 'a person',
}

/** Where a draft ranking came from, so a commit can say "proposed by …". Cleared as soon as
 * someone reorders by hand. */
type Origin = { source: ProposalSource; proposalId?: string; ranking: string[]; title: string }

export default function TriagePage() {
  const { data, isLoading } = useTriage()
  const { data: suggestions, isLoading: suggesting } = useSuggestions()
  const { projectId } = useScope()
  const [draft, setDraft] = useState<string[] | null>(null)
  const [origin, setOrigin] = useState<Origin | null>(null)
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const { persona } = usePersona()
  const [reason, setReason] = useState('')
  const [raised, setRaised] = useState<{ flags: HotFlag[]; journal: number } | null>(null)
  const [advisor, setAdvisor] = useState<'suggest' | 'cutin' | 'ai' | null>(null)
  const commit = useCommitRanking()
  const setNeedBy = useSetNeedBy()

  const saved = useMemo(() => data?.projects.map((p) => p.depot_project_id) ?? [], [data])
  const order = draft ?? saved
  const dirty = draft !== null && draft.join() !== saved.join()
  const { data: preview, isFetching: previewing } = usePreview(dirty ? draft : null)
  const fromOrigin = origin && draft && origin.ranking.join() === draft.join() ? origin : null

  const rowsById = useMemo(() => new Map(data?.projects.map((p) => [p.depot_project_id, p]) ?? []), [data])
  const previewById = useMemo(() => new Map(preview?.projects.map((p) => [p.depot_project_id, p]) ?? []), [preview])
  const nameOf = (id: string) => rowsById.get(id)?.name ?? 'Unknown project'

  function reorder(from: number, to: number) {
    if (to < 0 || to >= order.length || from === to) return
    setRaised(null)
    setDraft(move(order, from, to))
  }

  function tryRanking(ranking: string[], o: Omit<Origin, 'ranking'>) {
    setRaised(null)
    setDraft(ranking)
    setOrigin({ ...o, ranking })
    if (!reason) setReason(o.source === 'person' ? '' : `${SOURCE_LABEL[o.source]} suggestion: ${o.title}`)
  }

  function doCommit() {
    if (!draft || !persona) return
    commit.mutate(
      {
        order: draft,
        changed_by: persona.name,
        person_id: persona.id,
        reason: reason.trim(),
        source: fromOrigin?.source ?? 'person',
        proposal_id: fromOrigin?.proposalId,
      },
      {
        onSuccess: (res) => {
          setRaised({ flags: res.hot_flags_raised, journal: res.journal_posted })
          setDraft(null)
          setOrigin(null)
          setReason('')
        },
      },
    )
  }

  const lateNow = data?.projects.filter((p) => p.forecast.status === 'late' || p.forecast.status === 'blocked') ?? []

  return (
    <div className="page__content">
      <h1>Triage &amp; Impact</h1>
      <p className="page__sub">
        Leadership's stack rank of every manufacturing project. Rank 1 gets first call on shared work centers. Drag to try
        a different order, or try one of the suggestions below, and see the Impact on every need-by date before you
        commit it.
      </p>

      {isLoading ? (
        <p className="page__empty">Loading…</p>
      ) : !data || data.projects.length === 0 ? (
        <p className="page__empty">No manufacturing projects found yet.</p>
      ) : (
        <>
          {!dirty && (
            <div className="to-summary">
              <strong>{lateNow.length}</strong> of {data.projects.length} projects late or blocked at the current ranking.
              {data.bottleneck && (
                <>
                  {' '}
                  Bottleneck: <Link to="/constraints">{data.bottleneck}</Link>.
                </>
              )}
              <span className="basis-note">
                {' '}
                Forecast from S4 standard hours and work-center capacity, Mon–Fri, as of {shortDate(data.as_of)}.
              </span>
            </div>
          )}

          {raised && (
            <div className="to-banner">
              Ranking committed.{' '}
              {raised.flags.length === 0 ? (
                'No new hot flags: nothing new is in the way of the projects that moved up.'
              ) : (
                <>
                  {raised.flags.length} hot flag{raised.flags.length === 1 ? '' : 's'} raised on what's blocking the
                  projects that moved up. <Link to="/hot-flags">See hot flags →</Link>
                </>
              )}{' '}
              {raised.journal > 0 &&
                `Logged to the Journal on ${raised.journal} project${raised.journal === 1 ? '' : 's'}.`}
            </div>
          )}

          <AdvisorBar
            open={advisor}
            onOpen={setAdvisor}
            loading={suggesting || !suggestions}
            best={suggestions ? [...suggestions.proposals, ...suggestions.rankings][0] : undefined}
            cheapCount={suggestions?.cut_in.filter((c) => c.cheap).length ?? 0}
            onTryBest={(s) => tryRanking(s.ranking, { source: s.source, proposalId: s.id, title: s.title })}
          />
          {advisor && suggestions && (
            <div className="adv-panel">
              {advisor === 'suggest' &&
                ([...suggestions.proposals, ...suggestions.rankings].length === 0 ? (
                  <p className="page__empty">No ranking beats the current one on late projects and late days.</p>
                ) : (
                  [...suggestions.proposals, ...suggestions.rankings].map((s, i) => (
                    <SuggestionCard
                      key={s.id ?? `engine-${i}`}
                      s={s}
                      nameOf={nameOf}
                      onTry={() => tryRanking(s.ranking, { source: s.source, proposalId: s.id, title: s.title })}
                    />
                  ))
                ))}
              {advisor === 'cutin' && (
                <CutInTable
                  rows={suggestions.cut_in}
                  nameOf={nameOf}
                  onTry={(c) => tryRanking(c.ranking, { source: 'engine', title: `${c.name ?? 'Project'} to #1` })}
                />
              )}
              {advisor === 'ai' && (
                <AiPanel
                  kind="triage"
                  placeholder="e.g. Radar is contractual and can't slip. Nacelle has a customer escalation."
                />
              )}
            </div>
          )}

          {dirty && (
            <div className="to-commit card to-commit--sticky">
              <div className="to-commit__head">
                <strong>Proposed ranking</strong>
                {fromOrigin && <span className={`src-tag src-tag--${fromOrigin.source}`}>from {SOURCE_LABEL[fromOrigin.source]}</span>}
                <span className="basis-note">
                  {previewing ? 'Recomputing Impact…' : 'Impact shown against the saved ranking.'}
                </span>
              </div>
              {preview?.summary && (
                <p className="to-commit__summary">
                  Late days {preview.summary.late_days_before} → <strong>{preview.summary.late_days_after}</strong>
                  {preview.summary.recovered.length > 0 && (
                    <> · back on time: {preview.summary.recovered.map(nameOf).join(', ')}</>
                  )}
                  {preview.summary.newly_late.length > 0 && (
                    <span className="to-bad"> · goes late: {preview.summary.newly_late.map(nameOf).join(', ')}</span>
                  )}
                </p>
              )}
              <p className="to-commit__note">
                Committing raises hot flags on whatever is blocking each project you moved up, and logs the change to the
                Journal of every project whose rank or forecast moves.
              </p>
              <div className="to-commit__fields">
                <label className="field to-commit__reason">
                  Why the change
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Customer escalation on Nacelle delivery"
                  />
                </label>
              </div>
              {commit.error && <p className="to-error">{commit.error.message}</p>}
              <div className="to-commit__actions">
                <button
                  className="mt-btn mt-btn--ghost"
                  onClick={() => {
                    setDraft(null)
                    setOrigin(null)
                  }}
                >
                  Discard
                </button>
                <span className="to-commit__as">
                  as <strong>{persona?.name ?? '…'}</strong>
                </span>
                <button
                  className="mt-btn mt-btn--primary"
                  disabled={!persona || !reason.trim() || commit.isPending}
                  onClick={doCommit}
                >
                  {commit.isPending ? 'Committing…' : 'Commit ranking'}
                </button>
              </div>
            </div>
          )}

          <div className={`to-board card${dirty ? ' to-board--dirty' : ''}`}>
            <div className="to-row to-row--head">
              <span>Rank</span>
              <span>Project · work left</span>
              <span>Need by</span>
              <span>Forecast finish</span>
              <span>Slack</span>
              <span>Status</span>
              <span>Why</span>
            </div>
            {order.map((id, i) => {
              const row = rowsById.get(id)
              if (!row) return null
              return (
                <BoardRow
                  key={id}
                  index={i}
                  count={order.length}
                  row={row}
                  scoped={id === projectId}
                  preview={dirty ? previewById.get(id) : undefined}
                  dragging={dragIndex === i}
                  onDragStart={() => setDragIndex(i)}
                  onDragOver={() => {
                    if (dragIndex !== null && dragIndex !== i) {
                      reorder(dragIndex, i)
                      setDragIndex(i)
                    }
                  }}
                  onDragEnd={() => setDragIndex(null)}
                  onMove={(to) => reorder(i, to)}
                  onNeedBy={(value) => setNeedBy.mutate({ projectId: id, needBy: value || null })}
                />
              )
            })}
          </div>

          <h2 className="to-h2">Ranking history</h2>
          {data.history.length === 0 ? (
            <p className="page__empty">No re-ranks yet.</p>
          ) : (
            <ol className="to-history">
              {data.history.map((h) => (
                <li key={h.id} className="to-history__item">
                  <div className="to-history__meta">
                    <strong>{h.changed_by}</strong> · {shortDateTime(h.changed_at)}
                    {h.source !== 'person' && (
                      <span className={`src-tag src-tag--${h.source}`}>proposed by {SOURCE_LABEL[h.source]}</span>
                    )}
                  </div>
                  <div className="to-history__reason">{h.reason}</div>
                  <div className="to-history__order">
                    {h.after.map((pid, i) => {
                      const was = h.before.indexOf(pid)
                      const moved = was === -1 ? null : was - i
                      return (
                        <span key={pid} className="to-history__pill">
                          {i + 1}. {nameOf(pid)}
                          {moved ? (
                            <span className={moved > 0 ? 'to-up' : 'to-down'}>
                              {moved > 0 ? ` ▲${moved}` : ` ▼${-moved}`}
                            </span>
                          ) : null}
                        </span>
                      )
                    })}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  )
}

/** The top-of-page entry point to MARTI's suggestions, so they're reachable without scrolling
 * past the whole board: the best ranking it found (one click to preview), the cut-in check, and
 * Ask AI. Each opens its panel right under the bar. */
function AdvisorBar({
  open,
  onOpen,
  loading,
  best,
  cheapCount,
  onTryBest,
}: {
  open: 'suggest' | 'cutin' | 'ai' | null
  onOpen: (v: 'suggest' | 'cutin' | 'ai' | null) => void
  loading: boolean
  best: RankingSuggestion | undefined
  cheapCount: number
  onTryBest: (s: RankingSuggestion) => void
}) {
  const toggle = (v: 'suggest' | 'cutin' | 'ai') => onOpen(open === v ? null : v)
  return (
    <div className="adv-bar card">
      <span className="adv-bar__lead">
        {loading ? (
          'Working out suggestions…'
        ) : best ? (
          <>
            💡 <strong>{best.title}</strong>: late days {best.summary.late_days_before} → {best.summary.late_days_after}
            <button className="adv-bar__try" onClick={() => onTryBest(best)}>
              Preview
            </button>
          </>
        ) : (
          '💡 No ranking beats the current one.'
        )}
      </span>
      <span className="adv-bar__tabs">
        <button className={open === 'suggest' ? 'adv-bar__tab--on' : ''} onClick={() => toggle('suggest')}>
          Suggestions
        </button>
        <button className={open === 'cutin' ? 'adv-bar__tab--on' : ''} onClick={() => toggle('cutin')}>
          Cut in line{cheapCount > 0 && <span className="adv-bar__count">{cheapCount} cheap</span>}
        </button>
        <button className={open === 'ai' ? 'adv-bar__tab--on' : ''} onClick={() => toggle('ai')}>
          ✨ Ask AI
        </button>
      </span>
    </div>
  )
}

function SuggestionCard({ s, nameOf, onTry }: { s: RankingSuggestion; nameOf: (id: string) => string; onTry: () => void }) {
  return (
    <div className="sg-card card">
      <div className="sg-card__head">
        <span className={`src-tag src-tag--${s.source}`}>{SOURCE_LABEL[s.source]}</span>
        <strong className="sg-card__title">{s.title}</strong>
        <button className="mt-btn mt-btn--ghost" onClick={onTry}>
          Preview
        </button>
      </div>
      {s.rationale && <p className="sg-card__why">{s.rationale}</p>}
      <div className="sg-card__rows">
        {s.impact.map((r) => (
          <span key={r.depot_project_id} className="sg-card__row">
            {r.proposed.rank}. {nameOf(r.depot_project_id)}{' '}
            {r.finish_delta_days ? (
              <span className={r.finish_delta_days > 0 ? 'to-bad' : 'to-good'}>
                {r.finish_delta_days > 0 ? `+${r.finish_delta_days}d` : `${r.finish_delta_days}d`}
              </span>
            ) : null}{' '}
            <StatusChip status={r.proposed.status} />
          </span>
        ))}
      </div>
    </div>
  )
}

function CutInTable({ rows, nameOf, onTry }: { rows: CutIn[]; nameOf: (id: string) => string; onTry: (c: CutIn) => void }) {
  if (rows.length === 0) return null
  return (
    <div className="ci card">
      <div className="ci__head">
        <strong>Could it cut in line?</strong>
        <span className="basis-note">What each project gains if it goes to #1, and what everyone else pays.</span>
      </div>
      {rows.map((c) => (
        <div key={c.depot_project_id} className="ci__row">
          <span className="ci__name">
            #{c.current_rank} {c.name}
          </span>
          <span>
            {!c.forecastable ? (
              <span className="muted">Blocked: can't forecast</span>
            ) : c.gain_days > 0 ? (
              <span className="to-good">{c.gain_days}d sooner</span>
            ) : (
              <span className="muted">no gain</span>
            )}
          </span>
          <span>{c.cost_days > 0 ? `others lose ${c.cost_days}d` : <span className="muted">costs nobody</span>}</span>
          <span>
            {c.newly_late.length > 0 ? (
              <span className="to-bad">makes {c.newly_late.map(nameOf).join(', ')} late</span>
            ) : c.cheap ? (
              <span className="ci__cheap">Cheap to expedite</span>
            ) : null}
          </span>
          <button className="mt-btn mt-btn--ghost" onClick={() => onTry(c)} disabled={!c.forecastable}>
            Preview
          </button>
        </div>
      ))}
    </div>
  )
}

function BoardRow({
  index,
  count,
  row,
  scoped,
  preview,
  dragging,
  onDragStart,
  onDragOver,
  onDragEnd,
  onMove,
  onNeedBy,
}: {
  index: number
  count: number
  row: ProjectRow
  scoped: boolean
  preview: PreviewRow | undefined
  dragging: boolean
  onDragStart: () => void
  onDragOver: () => void
  onDragEnd: () => void
  onMove: (to: number) => void
  onNeedBy: (value: string) => void
}) {
  const f = preview?.proposed ?? row.forecast
  const delta = preview?.finish_delta_days
  const rankDelta = preview?.rank_delta ?? 0
  const statusChanged = preview && preview.proposed.status !== preview.current.status
  const sz = row.size
  const { setProjectId } = useScope()

  return (
    <div
      className={`to-row${dragging ? ' to-row--dragging' : ''}${rankDelta ? ' to-row--moved' : ''}${scoped ? ' to-row--scoped' : ''}`}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = 'move'
        onDragStart()
      }}
      onDragOver={(e) => {
        e.preventDefault()
        onDragOver()
      }}
      onDragEnd={onDragEnd}
    >
      <span className="to-rank">
        <span className="to-grip" title="Drag to reorder" aria-hidden="true">
          ⋮⋮
        </span>
        <span className="to-rank__num">{index + 1}</span>
        <span className="to-rank__arrows">
          <button aria-label="Move up" disabled={index === 0} onClick={() => onMove(index - 1)}>
            ▲
          </button>
          <button aria-label="Move down" disabled={index === count - 1} onClick={() => onMove(index + 1)}>
            ▼
          </button>
        </span>
        {rankDelta !== 0 && (
          <span className={rankDelta > 0 ? 'to-up' : 'to-down'}>{rankDelta > 0 ? `▲${rankDelta}` : `▼${-rankDelta}`}</span>
        )}
      </span>

      <span className="to-project">
        <Link to="/routing" className="to-project__name" onClick={() => setProjectId(row.depot_project_id)}>
          {row.name ?? 'Unknown project'}
        </Link>
        <span
          className="to-project__facts"
          title="Work left, from S4 routings: parts (open production orders), operations, and standard hours, with the share on the bottleneck"
        >
          {sz.parts_left} part{sz.parts_left === 1 ? '' : 's'} · {sz.ops_left} ops · {sz.std_hours_left} std h
          {sz.bottleneck && sz.bottleneck_hours_left > 0 && (
            <>
              {' '}
              · <strong>{sz.bottleneck_hours_left} h</strong> on {sz.bottleneck}
            </>
          )}
        </span>
        <span className="to-project__badges" draggable onDragStart={(e) => e.preventDefault()}>
          <IssueBadges projectId={row.depot_project_id} issues={row.issues} />
        </span>
      </span>

      <span>
        <input
          type="date"
          className="input to-needby"
          defaultValue={row.forecast.need_by ?? ''}
          key={row.forecast.need_by ?? 'none'}
          onBlur={(e) => {
            if (e.target.value !== (row.forecast.need_by ?? '')) onNeedBy(e.target.value)
          }}
        />
      </span>

      <span className="to-finish">
        {shortDate(f.projected_finish)}
        {delta != null && delta !== 0 && (
          <span className={`to-delta ${delta > 0 ? 'to-delta--worse' : 'to-delta--better'}`}>
            {delta > 0 ? `+${delta}d later` : `${-delta}d sooner`}
          </span>
        )}
      </span>

      <span>
        <SlackValue days={f.slack_days} />
      </span>

      <span className="to-status">
        <StatusChip status={f.status} />
        {statusChanged && <span className="to-was">was {preview.current.status.replace('_', ' ')}</span>}
      </span>

      <span className="to-why">
        <ImpactReason forecast={f} />
      </span>
    </div>
  )
}
