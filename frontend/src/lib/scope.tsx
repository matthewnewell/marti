import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

/** The project picker: which project Material & Acquisition and Routing are scoped to (null =
 * every manufacturing project). Remembered per browser, and a `?project=` in the URL (the Depot's
 * Launchpad tiles link that way) sets it on arrival. */

const STORAGE_KEY = 'marti.project'

interface ScopeValue {
  projectId: string | null
  setProjectId: (id: string | null) => void
}

const ScopeContext = createContext<ScopeValue | undefined>(undefined)

function readStored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function ScopeProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams()
  // A link from the Depot (it always carries `from`) that names no project means "the whole
  // shop", so it clears whatever project was picked last time instead of silently keeping it.
  const [projectId, setState] = useState<string | null>(() =>
    params.get('project') ?? (params.get('from') !== null ? null : readStored()),
  )

  function setProjectId(id: string | null) {
    setState(id)
    try {
      if (id) window.localStorage.setItem(STORAGE_KEY, id)
      else window.localStorage.removeItem(STORAGE_KEY)
    } catch {
      // storage unavailable: the choice just won't survive a reload
    }
  }

  useEffect(() => {
    if (!params.get('project') && params.get('from') !== null) setProjectId(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Adopt a ?project= from the URL, then drop it so the address bar stays clean.
  const fromUrl = params.get('project')
  useEffect(() => {
    if (fromUrl) {
      setProjectId(fromUrl)
      const next = new URLSearchParams(params)
      next.delete('project')
      setParams(next, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromUrl])

  return <ScopeContext.Provider value={{ projectId, setProjectId }}>{children}</ScopeContext.Provider>
}

export function useScope(): ScopeValue {
  const v = useContext(ScopeContext)
  if (!v) throw new Error('useScope must be used inside ScopeProvider')
  return v
}
