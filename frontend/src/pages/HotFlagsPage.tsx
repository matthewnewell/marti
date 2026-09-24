import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useHotFlags } from '../api/hooks'
import FlagCard from '../components/FlagCard'
import './HotFlagsPage.css'

export default function HotFlagsPage() {
  const [filter, setFilter] = useState<'active' | 'all'>('active')
  const { data, isLoading } = useHotFlags(filter)
  const flags = data?.hot_flags ?? []

  return (
    <div className="page__content hf">
          <h1>Hot flags</h1>
          <p className="page__sub">
            Expedite requests MARTI raises when leadership moves a project up in <Link to="/triage">Triage</Link>: late
            material goes to the buyer, a queued or held job goes to its work center. The owner acknowledges it, then
            resolves it once it's cleared.
          </p>

          <div className="hf__filter">
            <button className={filter === 'active' ? 'hf__f--on' : ''} onClick={() => setFilter('active')}>
              Active
            </button>
            <button className={filter === 'all' ? 'hf__f--on' : ''} onClick={() => setFilter('all')}>
              All
            </button>
          </div>

          {isLoading ? (
            <p className="page__empty">Loading…</p>
          ) : flags.length === 0 ? (
            <p className="page__empty">
              {filter === 'active'
                ? 'No active hot flags. Move a project up in Triage and commit to raise them.'
                : 'No hot flags yet.'}
            </p>
          ) : (
            <div className="hf__list">
              {flags.map((f) => (
                <FlagCard key={f.id} flag={f} showProject />
              ))}
            </div>
          )}
    </div>
  )
}
