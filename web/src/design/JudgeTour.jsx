import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { DESIGN_FLAGS } from './flags.js'
import './design.css'

const STEPS = [
  { path: '/room', target: '.room-chart', title: 'Engine decides, LLM speaks', body: 'The negotiation engine evaluates each offer. NegoAI communicates the decisions; it does not invent prices.' },
  { path: '/room', target: '.call-rail', title: 'Simulated vendors', body: 'Each supplier is simulated. The call rail shows the observed progress, one supplier at a time.' },
  { path: '/admin', target: '.trust-strip', title: 'AI disclosure', body: 'The approval screen explains what is AI-generated, what is simulated, and what the agent cannot approve.' },
  { path: '/replay', target: '.replay-v2', title: 'Tamper-evident proof', body: 'Select a stored replay to inspect its event timeline and receipt proof. No live vendor is involved.' },
]

const STORAGE_KEY = 'negoai-judge-tour-dismissed'

function isDismissed() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export default function JudgeTour() {
  const location = useLocation()
  const navigate = useNavigate()
  const requested = new URLSearchParams(location.search).get('tour') === '1'
  const [active, setActive] = useState(() => DESIGN_FLAGS.tour && requested && !isDismissed())
  const [stepIndex, setStepIndex] = useState(0)
  const [rect, setRect] = useState(null)
  const cardRef = useRef(null)

  useEffect(() => {
    if (DESIGN_FLAGS.tour && requested && !isDismissed()) setActive(true)
  }, [requested])

  useEffect(() => {
    if (!active) return
    const step = STEPS[stepIndex]
    if (location.pathname !== step.path) {
      navigate(`${step.path}?tour=1`, { replace: true })
      return
    }

    let timer
    let attempts = 0
    let target = null
    const updateRect = () => {
      if (!target) return
      const bounds = target.getBoundingClientRect()
      setRect({ top: bounds.top, left: bounds.left, width: bounds.width, height: bounds.height })
    }
    const findTarget = () => {
      if (stepIndex === 3 && !document.querySelector('.replay-v2')) {
        document.querySelector('.replay__row')?.click()
      }
      target = document.querySelector(step.target)
      attempts += 1
      if (target) {
        target.scrollIntoView({
          block: 'center',
          inline: 'nearest',
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        })
        timer = window.setTimeout(() => {
          updateRect()
          window.addEventListener('resize', updateRect)
          window.addEventListener('scroll', updateRect, true)
        }, 120)
      } else if (attempts < 40) {
        timer = window.setTimeout(findTarget, 150)
      } else {
        setRect(null)
      }
    }
    timer = window.setTimeout(findTarget, 100)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('resize', updateRect)
      window.removeEventListener('scroll', updateRect, true)
    }
  }, [active, stepIndex, location.pathname, navigate])

  useEffect(() => {
    if (active) cardRef.current?.querySelector('button')?.focus()
  }, [active, stepIndex])

  if (!DESIGN_FLAGS.tour || !active) return null

  function dismiss() {
    try {
      sessionStorage.setItem(STORAGE_KEY, '1')
    } catch {
      // The tour remains dismissible even when session storage is unavailable.
    }
    setActive(false)
    setRect(null)
    navigate(location.pathname, { replace: true })
  }

  const step = STEPS[stepIndex]
  const advance = (nextIndex) => {
    if (nextIndex >= STEPS.length) {
      dismiss()
      return
    }
    setRect(null)
    setStepIndex(nextIndex)
    const next = STEPS[nextIndex]
    if (location.pathname !== next.path) navigate(`${next.path}?tour=1`)
  }
  const keepFocusInside = (event) => {
    if (event.key === 'Escape') {
      dismiss()
      return
    }
    if (event.key !== 'Tab' || !cardRef.current) return
    const buttons = [...cardRef.current.querySelectorAll('button')]
    if (!buttons.length) return
    const first = buttons[0]
    const last = buttons[buttons.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div className="judge-tour" role="dialog" aria-modal="true" aria-labelledby="judge-tour-title"
      aria-describedby="judge-tour-copy" onKeyDown={keepFocusInside}>
      <div className={`judge-tour__shade ${rect ? 'is-spotlit' : ''}`} />
      {rect ? <div className="judge-tour__spotlight" style={rect} aria-hidden="true" /> : null}
      <section className="judge-tour__card" ref={cardRef}>
        <p className="design-kicker">Judge tour · {stepIndex + 1} of {STEPS.length}</p>
        <h2 id="judge-tour-title">{step.title}</h2>
        <p id="judge-tour-copy">{step.body}</p>
        <div className="judge-tour__actions">
          <button type="button" className="btn-outline" onClick={dismiss}>Skip tour</button>
          {stepIndex > 0 ? <button type="button" className="btn-outline" onClick={() => advance(stepIndex - 1)}>Back</button> : null}
          <button type="button" className="btn-solid" onClick={() => advance(stepIndex + 1)}>
            {stepIndex === STEPS.length - 1 ? 'Done' : 'Next'}
          </button>
        </div>
      </section>
    </div>
  )
}
