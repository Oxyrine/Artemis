import { ArrowUpRight, BookOpen, CircleHelp, Files, GitBranch, Moon, PanelLeftClose, PanelLeftOpen, ShieldCheck, Sun } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useReviewer, useTheme } from './providers'

const link = ({ isActive }: { isActive: boolean }) =>
  `workspace-link ${isActive ? 'is-active' : ''}`

export function Layout() {
  const { theme, toggle } = useTheme()
  const { reviewerId } = useReviewer()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const page = location.pathname.startsWith('/cases/') ? 'Case review' : location.pathname === '/audit' ? 'Audit ledger' : 'Reconciliation'
  return (
    <div className="workspace">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:shadow">
        Skip to content
      </a>
      <aside className={`workspace-sidebar ${menuOpen ? 'menu-open' : ''}`} id="workspace-navigation">
          <NavLink to="/" className="brand" onClick={() => setMenuOpen(false)} aria-label="Artemis home">
            <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 25 16 5l11 20M10 17h12M8 25l8-8 8 8" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>
            <span>artemis<span className="brand-period">.</span></span>
          </NavLink>
          <div className="workspace-scope"><span className="scope-dot" />Receivables workspace<span className="scope-unit">INR</span></div>
          <div className="nav-group-label">Workspace</div>
          <nav aria-label="Main" onClick={() => setMenuOpen(false)}>
            <NavLink to="/" end className={link}><Files size={17} />Reconciliation<ArrowUpRight className="nav-arrow" size={14} /></NavLink>
            <NavLink to="/audit" className={link}><ShieldCheck size={17} />Audit ledger<ArrowUpRight className="nav-arrow" size={14} /></NavLink>
          </nav>
          <div className="sidebar-method"><GitBranch size={19} strokeWidth={1.5} /><p>Every decision,<br /><strong>backed by evidence.</strong></p><span>Investigate. Reconcile. Review.</span></div>
          <div className="sidebar-bottom">
          <details className="workspace-help"><summary><CircleHelp size={16} />About this workspace</summary><p>Synthetic Indian receivables. Run an investigation, inspect the evidence, then record a named reviewer’s decision.</p></details>
          <div className="reviewer-identity"><span className="reviewer-initial">{reviewerId === 'controller-1' ? 'CC' : 'AA'}</span><div><strong>{reviewerId === 'controller-1' ? 'Chandra Controller' : 'Asha Analyst'}</strong><span>Demo reviewer</span></div>
          <Button variant="ghost" size="icon" onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
            {theme === 'dark' ? <Sun /> : <Moon />}
          </Button>
          </div></div>
      </aside>
      <div className="workspace-canvas">
        <header className="workspace-topbar"><Button className="mobile-menu" variant="ghost" size="icon" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <PanelLeftClose /> : <PanelLeftOpen />}</Button><span className="breadcrumb-root">Workspace</span><span className="breadcrumb-divider">/</span><span>{page}</span><span className="environment-label"><span />Synthetic environment</span></header>
        <main id="main" className="workspace-main" tabIndex={-1}><Outlet /></main>
        <footer className="workspace-footer"><span><BookOpen size={14} />Synthetic benchmark data</span><p>Tax rules are configured, not advised. Check against Income Tax Department guidance.</p><span>Artemis · INR</span></footer>
      </div>
    </div>
  )
}
