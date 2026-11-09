import { useEffect, useMemo, useRef, useState } from 'react'
import AppShell from './AppShell.jsx'
import { inr } from '../lib/format.js'

const API = import.meta.env.VITE_API_URL || ''

function formatClock(ts) {
  const date = ts ? new Date(ts) : new Date()
  return date.toLocaleTimeString('en-IN', { hour12: false })
}

/**
 * Replay is free because every offer, counter and decision is an append-only
 * row. This screen streams a stored session's events back into the room.
 */
export default function Replay() {
  const [sessions, setSessions] = useState([])
  const [active, setActive] = useState(null)
  const [events, setEvents] = useState([])
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const timer = useRef(0)

  useEffect(() => {
    let cancelled = false
    fetch(`${API}/api/sessions`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) setSessions(data.sessions || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!active) return
    let cancelled = false
    setEvents([])
    setCursor(0)
    fetch(`${API}/api/sessions/${active.id}/events`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) setEvents(data.events || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [active])

  useEffect(() => {
    if (!active) {
      setReceipt(null)
      return
    }
    let cancelled = false
    fetch(`${API}/api/sessions/${active.id}/receipt`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) setReceipt(data)
      })
      .catch(() => {
        if (!cancelled) setReceipt(null)
      })
    return () => {
      cancelled = true
    }
  }, [active])

  useEffect(() => {
    if (!playing) return
    timer.current = setInterval(() => {
      setCursor((c) => {
        if (c >= events.length) {
          setPlaying(false)
          return c
        }
        return c + 1
      })
    }, 850)
    return () => clearInterval(timer.current)
  }, [playing, events.length])

  const visible = useMemo(() => events.slice(0, cursor), [events, cursor])
  const offers = visible.filter((e) => e.type === 'offer')
  const latest = offers[offers.length - 1]

  return (
    <AppShell orb={playing ? 'thinking' : 'idle'} level={0} footer={
      <>
        <span>Replay reads append-only negotiation_events</span>
        <span className="screen__footsep">·</span>
        <span>No live vendor involved</span>
      </>
    }>
      <header className="panel__head">
        <div>
          <p className="eyebrow">Audit trail</p>
          <h2 className="panel__title">Replay a negotiation</h2>
        </div>
        <div className="panel__meta">
          <span className="pill">{sessions.length} stored</span>
        </div>
      </header>

      <div className="panel__body">
        {error ? (
          <div className="notice notice--warn">
            Replay needs the FastAPI gateway. Start it with <code>uvicorn api.main:app</code> and
            reload. ({error})
          </div>
        ) : null}

        {sessions.length === 0 && !error ? (
          <p className="room__empty">No stored negotiations yet. Run the guided demo once.</p>
        ) : null}

        {sessions.map((session) => (
          <button
            key={session.id}
            type="button"
            className={`replay__row ${active?.id === session.id ? 'is-active' : ''}`}
            onClick={() => {
              setActive(session)
              setPlaying(false)
            }}
          >
            <span>
              {session.community || 'Community'} · {session.product || 'water can'}
              <small>
                {session.state} · {session.events ?? 0} events · {formatClock(session.created_at)}
              </small>
            </span>
            <span className="pill">{session.language || 'kn-IN'}</span>
          </button>
        ))}

        {active ? (
          <>
            <div className="replay__controls">
              <button
                type="button"
                className="btn-solid"
                onClick={() => {
                  if (cursor >= events.length) setCursor(0)
                  setPlaying((p) => !p)
                }}
                disabled={!events.length}
              >
                {playing ? 'Pause' : cursor >= events.length ? 'Replay' : 'Play'}
              </button>
              <button
                type="button"
                className="btn-outline"
                onClick={() => {
                  setPlaying(false)
                  setCursor(events.length)
                }}
                disabled={!events.length}
              >
                Skip to end
              </button>
              <span className="pill">
                {cursor} / {events.length} events
              </span>
              {latest?.payload?.unit_price != null ? (
                <span className="pill">Last quote {inr(latest.payload.unit_price)}</span>
              ) : null}
            </div>

            {receipt ? (
              <div className="replay__controls">
                <span className="pill">Tamper-evident · {receipt.event_count} events</span>
                <span className="pill">Savings {inr(receipt.savings)}</span>
                <span className="pill" title={receipt.chain_head}>
                  sha256 {String(receipt.chain_head).slice(0, 12)}…
                </span>
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => navigator.clipboard?.writeText(receipt.chain_head)}
                >
                  Copy proof
                </button>
              </div>
            ) : null}

            <div className="replay__events">
              {visible.map((event, i) => (
                <div className="replay__event" key={`${event.ts}-${i}`}>
                  <time>{formatClock(event.ts)}</time>
                  <span>
                    <strong>{event.actor}</strong> · {event.type}
                    {event.payload?.unit_price != null ? ` · ₹${event.payload.unit_price}` : ''}
                    {event.payload?.directive ? ` · ${event.payload.directive}` : ''}
                    {event.payload?.text ? ` · “${event.payload.text}”` : ''}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  )
}
