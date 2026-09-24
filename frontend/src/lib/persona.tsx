import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { usePeople } from '../api/hooks'
import type { DepotPerson } from '../api/types'

/**
 * Who's using MARTI: the "viewing as" persona from Conway's Depot's own people list, the same
 * switcher every app in the ecosystem shows. Not a login. It's who a Triage commit, a hot-flag
 * acknowledgement, a proposal decision and the Journal entries they write are credited to.
 * A Depot link names the person (`?person_id=`), which wins on arrival; otherwise the last
 * choice is remembered in this browser.
 */

const STORAGE_KEY = 'marti:person-id'

interface PersonaContextValue {
  persona: DepotPerson | null
  people: DepotPerson[]
  isLoading: boolean
  depotReachable: boolean
  setPersonId: (id: string) => void
}

const PersonaContext = createContext<PersonaContextValue | undefined>(undefined)

function readStoredId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function readUrlPersonId(): string | null {
  try {
    return new URLSearchParams(window.location.search).get('person_id')
  } catch {
    return null
  }
}

export function PersonaProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = usePeople()
  const [urlPersonId] = useState<string | null>(readUrlPersonId)
  const [personId, setPersonIdState] = useState<string | null>(readStoredId)

  function setPersonId(id: string) {
    setPersonIdState(id)
    try {
      window.localStorage.setItem(STORAGE_KEY, id)
    } catch {
      /* storage unavailable: the choice just won't persist */
    }
  }

  const people = useMemo(() => data?.people ?? [], [data])

  useEffect(() => {
    if (people.length === 0) return
    if (urlPersonId && people.some((p) => p.id === urlPersonId)) {
      if (personId !== urlPersonId) setPersonId(urlPersonId)
      return
    }
    if (people.some((p) => p.id === personId)) return
    const fallback = people.find((p) => p.is_admin) ?? people[0]
    setPersonId(fallback.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [people])

  const value = useMemo<PersonaContextValue>(
    () => ({
      persona: people.find((p) => p.id === personId) ?? null,
      people,
      isLoading,
      depotReachable: data?.depot_reachable ?? true,
      setPersonId,
    }),
    [people, personId, isLoading, data],
  )

  return <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>
}

export function usePersona(): PersonaContextValue {
  const ctx = useContext(PersonaContext)
  if (!ctx) throw new Error('usePersona must be used within a PersonaProvider')
  return ctx
}
