import { useEffect, useRef, useState } from 'react'
import type { Issue, TreeNode } from '../api/types'
import { shortDate } from '../lib/format'
import IssueBadges from './IssueBadges'
import { CTB_LABEL, OrderCard } from './OrderCard'
import './RoutingTree.css'

/** A project's production orders as an assembly tree (top assembly → sub → sub-sub, any depth).
 * Collapsed by default except along the critical chain, the orders setting the finish date.
 * "Problems only" hides branches with nothing held, waiting on material, carrying an open
 * quality notification, or critical. `focus` (an order number, from an issue link) opens the
 * path down to that order, opens its operations and scrolls to it. The badges on each row open
 * the problems in that branch, with who fixes them. */
export default function RoutingTree({
  roots,
  problemsOnly,
  focus,
  projectId,
  issues,
}: {
  roots: TreeNode[]
  problemsOnly: boolean
  focus: string | null
  projectId: string
  issues: Issue[]
}) {
  if (roots.length === 0) return <p className="page__empty">No production orders for this project.</p>
  return (
    <div className="rt card">
      <div className="rt__row rt__row--head">
        <span>Order</span>
        <span>Routing</span>
        <span>Status · problems</span>
        <span>Below</span>
        <span>Forecast done</span>
      </div>
      {roots.map((n) => (
        <Node key={n.order_id} node={n} depth={0} problemsOnly={problemsOnly} focus={focus} projectId={projectId} issues={issues} />
      ))}
    </div>
  )
}

function hasProblem(n: TreeNode): boolean {
  const r = n.rollup
  return n.critical || r.held > 0 || r.waiting_material > 0 || r.open_quality > 0
}

function orderNumbers(n: TreeNode): string[] {
  return [n.order_number, ...n.children.flatMap(orderNumbers)]
}

function Node({
  node,
  depth,
  problemsOnly,
  focus,
  projectId,
  issues,
}: {
  node: TreeNode
  depth: number
  problemsOnly: boolean
  focus: string | null
  projectId: string
  issues: Issue[]
}) {
  const below = orderNumbers(node)
  const focusBelow = !!focus && below.includes(focus)
  const isFocus = focus === node.order_number
  const [open, setOpen] = useState((node.critical || focusBelow) && node.children.length > 0)
  const [detail, setDetail] = useState(isFocus)
  const rowRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (isFocus) rowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [isFocus])
  // A row's badges cover its own order and everything under it.
  const mine = issues.filter((i) => i.order_number && below.includes(i.order_number) && i.kind !== 'flag')
  if (problemsOnly && !hasProblem(node) && !focusBelow) return null
  const r = node.rollup
  const done = node.clear_to_build.status === 'complete'
  const belowCount = r.orders - 1

  return (
    <>
      <div
        ref={rowRef}
        className={`rt__row${node.critical ? ' rt__row--critical' : ''}${done ? ' rt__row--done' : ''}${isFocus ? ' rt__row--focus' : ''}`}
      >
        <span className="rt__order" style={{ paddingLeft: depth * 22 }}>
          {node.children.length > 0 ? (
            <button className="rt__toggle" onClick={() => setOpen(!open)} aria-label={open ? 'Collapse' : 'Expand'}>
              {open ? '▾' : '▸'}
            </button>
          ) : (
            <span className="rt__toggle rt__toggle--leaf">·</span>
          )}
          <button className="rt__name" onClick={() => setDetail(!detail)} title="Show operations">
            <span className="mono rt__num">{node.order_number}</span> {node.description ?? node.material_number}
            <span className="muted"> ×{node.quantity}</span>
          </button>
          {node.critical && !done && (
            <span className="rt__crit" title="On the chain of orders setting this project's finish date">
              critical
            </span>
          )}
        </span>

        <span className="rt__strip" title={node.operations.map((o) => `${o.seq} ${o.description} (${o.work_center}): ${o.state}`).join('\n')}>
          {node.operations.map((o) => (
            <span
              key={o.id}
              className={`rt__op rt__op--${o.state}${o.seq === node.current_seq ? ' rt__op--here' : ''}`}
            />
          ))}
          <span className="rt__strip-label">
            {node.operations.filter((o) => o.state === 'done').length}/{node.operations.length}
          </span>
        </span>

        <span className="rt__status">
          <span className={`chip ctb--${node.clear_to_build.status}`}>{CTB_LABEL[node.clear_to_build.status]}</span>
          <IssueBadges projectId={projectId} issues={mine} />
        </span>

        <span className="rt__below">
          {belowCount > 0 ? (
            <>
              {r.complete}/{r.orders} orders
              {r.held > 0 && <span className="rt__bad"> · {r.held} held</span>}
              {r.waiting_material > 0 && <span className="rt__warn"> · {r.waiting_material} short</span>}
            </>
          ) : (
            <span className="muted">—</span>
          )}
        </span>

        <span className="rt__finish">
          {done ? 'Done' : node.forecast_blocked ? <span className="rt__bad">Blocked</span> : shortDate(node.forecast_finish_date)}
        </span>
      </div>

      {detail && (
        <div className="rt__detail" style={{ paddingLeft: 14 + depth * 22 }}>
          <OrderCard order={node} />
        </div>
      )}

      {open &&
        node.children.map((k) => (
          <Node
            key={k.order_id}
            node={k}
            depth={depth + 1}
            problemsOnly={problemsOnly}
            focus={focus}
            projectId={projectId}
            issues={issues}
          />
        ))}
    </>
  )
}
