import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import AppShell from './AppShell.jsx'
import { LanguageChips } from './SocialSquares.jsx'
import { useSession, LANGUAGES } from '../state/session.js'
import { voice } from '../lib/voice.js'
import { ROLE_LABEL } from '../lib/format.js'

const ease = [0.22, 1, 0.36, 1]
const API = import.meta.env.VITE_API_URL || ''

const QUICK = {
  'kn-IN': 'ನನಗೆ ವಾರಕ್ಕೆ ಮೂರು ನೀರಿನ ಕ್ಯಾನ್ ಬೇಕು',
  'hi-IN': 'मुझे हर हफ्ते तीन पानी के कैन चाहिए',
  'en-IN': 'Three water cans every week',
}

function MyRequests() {
  const demandSaved = useSession((s) => s.demandSaved)
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const count = demandSaved.length

  useEffect(() => {
    let cancelled = false
    fetch(`${API}/api/demand/requests?limit=5`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) {
          setRows(data.requests || [])
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [count])

  if (error || (!rows.length && !count)) return null

  return (
    <details className="requests" open={count > 0}>
      <summary>
        My requests <span className="pill">{rows.length} saved</span>
      </summary>
      {rows.map((row) => (
        <div className="requests__row" key={row.id}>
          <span>
            {row.qty} × {row.product}
          </span>
          <small>
            {row.frequency}
            {row.delivery_day ? ` · ${row.delivery_day}` : ''}
            {row.flat_number ? ` · ${row.flat_number}` : ''}
          </small>
          <span className="requests__lang">{row.language}</span>
        </div>
      ))}
    </details>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" strokeLinecap="round" />
    </svg>
  )
}

export default function VoiceConsole() {
  const status = useSession((s) => s.status)
  const language = useSession((s) => s.language)
  const orb = useSession((s) => s.orb)
  const level = useSession((s) => s.level)
  const lines = useSession((s) => s.lines)
  const partial = useSession((s) => s.partial)
  const confirm = useSession((s) => s.confirm)
  const notices = useSession((s) => s.notices)
  const micOn = useSession((s) => s.micOn)
  const community = useSession((s) => s.community)
  const [draft, setDraft] = useState('')
  const [langOpen, setLangOpen] = useState(false)
  const scrollRef = useRef(null)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    if (useSession.getState().status === 'idle') voice.startLive()
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines.length, partial, confirm])

  const submit = (event) => {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return
    voice.sendText(text)
    setDraft('')
  }

  const connected = status === 'ready'

  return (
    <AppShell orb={orb} level={level}>
      <header className="panel__head">
        <div>
          <p className="eyebrow">
            {community?.name} · {community?.households} households
          </p>
          <h2 className="panel__title">Voice console</h2>
        </div>
        <div className="panel__meta">
          <span className="pill">
            <span className={`dot-live ${connected ? '' : 'dot-live--off'}`} />
            {status === 'connecting' ? 'Connecting' : connected ? 'Live' : 'Offline'}
          </span>
          <button
            type="button"
            className="pill"
            onClick={() => setLangOpen((v) => !v)}
            aria-expanded={langOpen}
          >
            {LANGUAGES.find((l) => l.id === language)?.label || language} ▾
          </button>
        </div>
      </header>

      <div className="panel__body" ref={scrollRef}>
        <div className="transcript">
          {lines.length === 0 && (
            <div className="transcript__empty">
              <p>
                Ask for your weekly requirement the way you would talk to a neighbour — “three water
                cans every week”. NegoAI reads the quantity back in words, then negotiates on
                behalf of the whole society. It never confirms a price; the committee approves.
              </p>
            </div>
          )}

          {lines.map((line, index) => {
            const age = lines.length - 1 - index
            const opacity = Math.max(0.34, 1 - age * 0.06)
            return (
              <motion.div
                key={line.id}
                className={`line line--${line.role}`}
                style={{ opacity }}
                initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
                animate={{ opacity, y: 0, filter: 'blur(0px)' }}
                transition={{ duration: 0.5, ease }}
              >
                <div className="line__meta">
                  <strong>{line.vendor || ROLE_LABEL[line.role] || line.role}</strong>
                  {line.lang ? <span>{line.lang}</span> : null}
                  {index === lines.length - 1 ? <span>newest</span> : null}
                </div>
                <p className="line__text">{line.text}</p>
                {line.subtitle && line.subtitle !== line.text ? (
                  <p className="line__gloss">{line.subtitle}</p>
                ) : null}
              </motion.div>
            )
          })}

          {partial ? (
            <div className="line line--resident line--partial">
              <div className="line__meta">
                <strong>You</strong>
                <span>{language}</span>
              </div>
              <p className="line__text">{partial}…</p>
            </div>
          ) : null}
        </div>

        {notices.length > 0 && (
          <div className="notices">
            {notices.map((notice) => (
              <p key={notice.id} className={`notice ${notice.level === 'warn' ? 'notice--warn' : ''}`}>
                {notice.text}
              </p>
            ))}
          </div>
        )}

        <MyRequests />
      </div>

      <AnimatePresence>
        {confirm && (
          <motion.div
            className="confirm"
            initial={{ opacity: 0, y: 16, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: 10, height: 0 }}
            transition={{ duration: 0.45, ease }}
          >
            <p className="confirm__question">{confirm.text}</p>
            <p className="confirm__hint">Confirm before it counts</p>
            <div className="confirm__actions">
              <button type="button" className="btn-solid" onClick={() => voice.sendText('yes, correct')}>
                Yes, confirm
              </button>
              <button type="button" className="btn-outline btn-outline--ink" onClick={() => voice.sendText('no, change it')}>
                Change it
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="panel__foot">
        <div className="composer">
          <button
            type="button"
            className={`mic-btn ${micOn ? 'is-live' : ''}`}
            onClick={voice.toggleMic}
            aria-label={micOn ? 'Stop microphone' : 'Start microphone'}
            aria-pressed={micOn}
          >
            <MicIcon />
          </button>

          <form className="composer__form" onSubmit={submit}>
            <input
              className="composer__input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type your demand — same agent, same brain"
              aria-label="Type your demand"
            />
            <button type="submit" className="composer__send" aria-label="Send">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M4 12h15M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>

          <button
            type="button"
            className="btn-outline"
            onClick={() => voice.startDemo(language)}
            title="Run the guided negotiation end to end"
          >
            Guided demo
          </button>
        </div>

        <div className="quick-prompts">
          <button type="button" onClick={() => voice.sendText(QUICK[language] || QUICK['en-IN'])}>
            “{QUICK[language] || QUICK['en-IN']}”
          </button>
          <Link to="/room" className="pill" style={{ alignSelf: 'center' }}>
            Open negotiation room →
          </Link>
        </div>
      </div>

      <LanguageChips
        open={langOpen}
        value={language}
        onChange={(lang) => {
          voice.setLanguage(lang)
          setLangOpen(false)
        }}
        align="left"
      />
    </AppShell>
  )
}
