import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useSession } from '../state/session.js'
import { voice } from '../lib/voice.js'
import FurTorus from './FurTorus.jsx'
import Logo from './Logo.jsx'
import '../styles/screens.css'

const NAV = [
  { to: '/console', label: 'Console' },
  { to: '/room', label: 'Room' },
  { to: '/admin', label: 'Approval' },
  { to: '/replay', label: 'Replay' },
]

const STATE_COPY = {
  idle: 'Idle — waiting for you',
  listening: 'Listening…',
  thinking: 'Negotiating internally…',
  speaking: 'Speaking',
}

export default function AppShell({ children, orb = 'idle', level = 0, footer = null }) {
  const location = useLocation()
  const sessionStartedAt = useSession((s) => s.sessionStartedAt)
  const status = useSession((s) => s.status)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  const elapsed = sessionStartedAt ? Math.max(0, Math.floor((now - sessionStartedAt) / 1000)) : 0
  const sessionWarning = elapsed >= 240
  const demoEnabled = new URLSearchParams(location.search).get('demo') === '1'

  return (
    <main className={`screen ${demoEnabled ? 'screen--demo' : ''}`}>
      <header className="screen__top">
        <Link to="/" className="screen__brand" aria-label="NegoAI home">
          <Logo compact tone="dark" />
          <span>negoai</span>
        </Link>
        <nav className="screen__nav" aria-label="App sections">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `screen__navlink ${isActive ? 'is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        {sessionStartedAt ? (
          <span className={`session-time ${sessionWarning ? 'session-time--warning' : ''}`}>
            Session {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}
            {sessionWarning ? ' · reconnect soon' : ''}
          </span>
        ) : null}
        {sessionStartedAt && status === 'idle' ? (
          <button type="button" className="session-resume" onClick={() => voice.resume()}>
            Connection dropped. Tap to continue
          </button>
        ) : null}
      </header>

      <div className="screen__card">
        <section className="screen__panel">{children}</section>
        <aside className="screen__stage" aria-hidden="true">
          <div className="screen__orb">
            <FurTorus state={orb} level={level} />
          </div>
          <motion.p
            className="stage__state"
            key={orb}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <span className={`dot-live ${orb === 'idle' ? 'dot-live--off' : ''}`} />
            {STATE_COPY[orb] || orb}
          </motion.p>
        </aside>
        <div className="grain" />
      </div>

      <footer className="screen__foot">
        {footer || (
          <>
            <span>Powered by Gnani Prisma + Timbre</span>
            <span className="screen__footsep">·</span>
            <span>All vendors simulated · synthetic data only</span>
          </>
        )}
      </footer>
    </main>
  )
}
