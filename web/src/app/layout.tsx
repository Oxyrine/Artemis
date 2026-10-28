import { BookOpen, Compass, Menu, Moon, Sun, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { DemoGuide } from '@/features/guide/DemoGuide'
import { BatchProvider } from '@/features/dashboard/BatchProvider'
import { GuideProvider, useGuide } from '@/features/guide/GuideProvider'
import { useTheme } from './providers'

const link = ({ isActive }: { isActive: boolean }) =>
  `workspace-link ${isActive ? 'is-active' : ''}`

export function Layout() {
  return <GuideProvider><BatchProvider><Shell /></BatchProvider></GuideProvider>
}

function Shell() {
  const guide = useGuide()
  const reviewingCase = useLocation().pathname.startsWith('/cases/')
  const { theme, toggle } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuButton = useRef<HTMLButtonElement>(null)
  return (
    <div className="workspace">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>
      <header className={`floating-navigation ${menuOpen ? 'menu-open' : ''}`}
        onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setMenuOpen(false) }}
        onKeyDown={(event) => { if (event.key === 'Escape' && menuOpen) { setMenuOpen(false); menuButton.current?.focus() } }}>
        <NavLink to="/" className="brand" onClick={() => setMenuOpen(false)} aria-label="Artemis home">
          <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 25 16 5l11 20M10 17h12M8 25l8-8 8 8" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>
          <span>artemis<span className="brand-period">.</span></span>
        </NavLink>
        <nav id="workspace-navigation" aria-label="Main" onClick={() => setMenuOpen(false)}>
          <NavLink to="/" end className={({ isActive }) => link({ isActive: isActive || reviewingCase })}>Reconciliation</NavLink>
          <NavLink to="/compare" className={link}>Agent paths</NavLink>
          <NavLink to="/audit" className={link}>Audit ledger</NavLink>
        </nav>
        <div className="navigation-actions">
          <button type="button" className="guide-launch" aria-label="Guided demo" onClick={() => { guide.start(); setMenuOpen(false) }}><Compass size={16} /><span>Guided demo</span></button>
          <Button variant="ghost" size="icon" onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
            {theme === 'dark' ? <Sun /> : <Moon />}
          </Button>
          <Button ref={menuButton} className="mobile-menu" variant="ghost" size="icon" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</Button>
        </div>
      </header>
      <div className="workspace-canvas">
        <main id="main" className="workspace-main" tabIndex={-1}><Outlet /></main>
        <footer className="workspace-footer"><span><BookOpen size={14} />Synthetic benchmark data</span><p>Tax rules are configured, not advised. Check against Income Tax Department guidance.</p><span>Artemis · INR</span></footer>
      </div>
      <DemoGuide />
    </div>
  )
}
