import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useSession } from '../state/session.js'
import { voice } from '../lib/voice.js'

const PHASE_ROUTE = {
  negotiation: '/room',
  approval: '/admin',
}

/**
 * ?demo=1 — a floating director that starts the preloaded synthetic scenario
 * and follows it across screens. Built for recording the 60-second shot list.
 */
export default function DemoBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const phase = useSession((s) => s.phase)
  const demoRunning = useSession((s) => s.demoRunning)
  const language = useSession((s) => s.language)
  const orb = useSession((s) => s.orb)

  const enabled = new URLSearchParams(location.search).get('demo') === '1'

  useEffect(() => {
    if (!enabled || !demoRunning) return
    const target = PHASE_ROUTE[phase]
    if (target && location.pathname !== target) {
      navigate(`${target}?demo=1`)
    }
  }, [phase, demoRunning, enabled, location.pathname, navigate])

  if (!enabled) return null

  return (
    <AnimatePresence>
      <motion.div
        className="demobar"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <span className="demobar__phase">
          <span className={`dot-live ${orb === 'idle' ? 'dot-live--off' : ''}`} />
          Demo · {phase}
        </span>
        <button type="button" className="demobar__btn" onClick={() => voice.startDemo(language)}>
          {demoRunning ? 'Restart' : 'Start demo'}
        </button>
        <button type="button" className="demobar__btn demobar__btn--ghost" onClick={() => voice.reset()}>
          Reset
        </button>
        <button
          type="button"
          className="demobar__btn demobar__btn--ghost"
          onClick={() => navigate(`/console?demo=1`)}
        >
          Console
        </button>
      </motion.div>
    </AnimatePresence>
  )
}
