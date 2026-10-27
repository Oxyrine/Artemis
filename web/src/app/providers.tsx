import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

// Per-viewer conveniences only (theme, which reviewer is acting): localStorage may be blocked, so every access is guarded.
const read = (k: string): string | null => { try { return localStorage.getItem(k) } catch { return null } }
const write = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* private window: keep in memory */ } }

type Theme = 'light' | 'dark'
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void }>({ theme: 'light', toggle: () => {} })
export const useTheme = () => useContext(ThemeCtx)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = read('artemis.theme')
    if (saved === 'dark' || saved === 'light') return saved
    return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    write('artemis.theme', theme)
  }, [theme])
  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), [])
  return <ThemeCtx.Provider value={useMemo(() => ({ theme, toggle }), [theme, toggle])}>{children}</ThemeCtx.Provider>
}

// The acting reviewer is a stub: an X-Reviewer-Id chosen from a dropdown (the server still enforces policy and limits).
const ReviewerCtx = createContext<{ reviewerId: string; setReviewerId: (id: string) => void }>({
  reviewerId: 'analyst-1', setReviewerId: () => {},
})
export const useReviewer = () => useContext(ReviewerCtx)

export function ReviewerProvider({ children }: { children: ReactNode }) {
  const [reviewerId, setId] = useState(() => read('artemis.reviewer') ?? 'analyst-1')
  const setReviewerId = useCallback((id: string) => { setId(id); write('artemis.reviewer', id) }, [])
  return <ReviewerCtx.Provider value={useMemo(() => ({ reviewerId, setReviewerId }), [reviewerId, setReviewerId])}>{children}</ReviewerCtx.Provider>
}
