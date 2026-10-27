import { Moon, Sun } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useTheme } from './providers'

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted ${isActive ? 'bg-muted text-foreground' : 'text-muted-foreground'}`

export function Layout() {
  const { theme, toggle } = useTheme()
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span aria-hidden className="grid size-6 place-items-center rounded-md bg-primary text-xs text-primary-foreground">A</span>
            Artemis
          </NavLink>
          <nav aria-label="Main" className="flex gap-1">
            <NavLink to="/" end className={link}>Dashboard</NavLink>
            <NavLink to="/audit" className={link}>Audit</NavLink>
          </nav>
          <Button variant="ghost" size="icon" className="ml-auto" onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
            {theme === 'dark' ? <Sun /> : <Moon />}
          </Button>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 py-6"><Outlet /></main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-muted-foreground">
        Synthetic benchmark data. Tax rules are configured, not advised: check them against the Income Tax Department&apos;s guidance.
      </footer>
    </>
  )
}
