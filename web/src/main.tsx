import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// A tab left open across a deploy asks for chunk files that no longer exist (the host answers with index.html). Reload once
// to pick up the new build; the flag stops a reload loop if the chunk is genuinely broken.
window.addEventListener('vite:preloadError', (e) => {
  e.preventDefault()
  try {
    if (sessionStorage.getItem('artemis.reloaded') === '1') return
    sessionStorage.setItem('artemis.reloaded', '1')
  } catch { /* storage unavailable: reload anyway, once per page load is all this can do */ }
  window.location.reload()
})
window.addEventListener('load', () => window.setTimeout(() => { try { sessionStorage.removeItem('artemis.reloaded') } catch { /* ignore */ } }, 10_000))

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
