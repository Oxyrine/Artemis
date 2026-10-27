import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { GUIDE_STEPS } from '@/lib/guide'

type Guide = { active: boolean; step: number; start: () => void; stop: () => void; go: (n: number) => void }
const Ctx = createContext<Guide | null>(null)
const KEY = 'artemis.guide'

function load(): { active: boolean; step: number } {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? 'null')
    if (v && typeof v.step === 'number') return { active: !!v.active, step: Math.min(Math.max(v.step, 0), GUIDE_STEPS.length - 1) }
  } catch { /* storage can be unavailable (private windows): the guide just starts closed */ }
  return { active: false, step: 0 }
}

/** The guided demo's state lives above the router outlet so it survives navigation between pages. */
export function GuideProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState(load)
  const save = useCallback((next: { active: boolean; step: number }) => {
    setS(next)
    try { sessionStorage.setItem(KEY, JSON.stringify(next)) } catch { /* see load() */ }
  }, [])
  const value = useMemo<Guide>(() => ({
    ...s,
    start: () => save({ active: true, step: 0 }),
    stop: () => save({ active: false, step: s.step }),
    go: (n) => save({ active: true, step: Math.min(Math.max(n, 0), GUIDE_STEPS.length - 1) }),
  }), [s, save])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useGuide(): Guide {
  const g = useContext(Ctx)
  if (!g) throw new Error('useGuide must be used inside GuideProvider')
  return g
}
