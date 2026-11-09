import { useMemo } from 'react'
import { inr } from '../lib/format.js'
import { DESIGN_FLAGS } from './flags.js'
import './design.css'

const EVENT_COLORS = {
  offer: '#12634d',
  counter: '#9a6200',
  decision: '#512672',
  phase: '#3b1a5e',
}

function pricePoints(events, cursor) {
  const prices = events
    .map((event, index) => ({ index, price: event.payload?.unit_price }))
    .filter((point) => point.index < cursor && typeof point.price === 'number' && Number.isFinite(point.price))
  if (!prices.length) return { points: [], latest: null, min: 0, max: 0 }
  const values = prices.map((point) => point.price)
  return { points: prices, latest: prices[prices.length - 1], min: Math.min(...values), max: Math.max(...values) }
}

function eventColor(type) {
  if (type === 'offer' || type === 'quote') return EVENT_COLORS.offer
  if (/counter/i.test(type || '')) return EVENT_COLORS.counter
  if (/decision|admin|approval/i.test(type || '')) return EVENT_COLORS.decision
  return EVENT_COLORS.phase
}

export default function ReplayExperience({ events, cursor, setCursor, playing, setPlaying, speed, setSpeed }) {
  const chart = useMemo(() => pricePoints(events, cursor), [events, cursor])
  if (!DESIGN_FLAGS.replay) return null

  const onKeyDown = (event) => {
    if (event.target !== event.currentTarget) return
    if (event.key === ' ') {
      event.preventDefault()
      if (cursor >= events.length) setCursor(0)
      setPlaying((value) => !value)
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault()
      setPlaying(false)
      setCursor((value) => Math.max(0, value - 1))
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      setPlaying(false)
      setCursor((value) => Math.min(events.length, value + 1))
    }
  }

  const maxIndex = Math.max(events.length, 1)
  const points = chart.points.map((point) => {
    const x = 26 + (point.index / maxIndex) * 548
    const spread = chart.max - chart.min
    const y = spread === 0 ? 50 : 88 - ((point.price - chart.min) / spread) * 70
    return `${x},${y}`
  }).join(' ')
  const cursorX = 26 + (cursor / maxIndex) * 548

  return (
    <section className="replay-v2" tabIndex={0} onKeyDown={onKeyDown}
      aria-label="Replay timeline. Focus this panel and use space to play or pause, and arrow keys to step.">
      <div className="replay-v2__toolbar">
        <button type="button" className="btn-solid" disabled={!events.length}
          onClick={() => {
            if (cursor >= events.length) setCursor(0)
            setPlaying((value) => !value)
          }}>{playing ? 'Pause' : cursor >= events.length ? 'Replay' : 'Play'}</button>
        <button type="button" className="btn-outline" disabled={!events.length}
          onClick={() => { setPlaying(false); setCursor(events.length) }}>Skip to end</button>
        <span className="pill">{cursor} / {events.length} events</span>
        <div className="replay-v2__speed" aria-label="Playback speed">
          {[1, 2, 4].map((rate) => (
            <button type="button" key={rate} aria-pressed={speed === rate}
              className={speed === rate ? 'is-selected' : ''} onClick={() => setSpeed(rate)}>{rate}x</button>
          ))}
        </div>
      </div>

      <label className="replay-v2__range-label" htmlFor="replay-timeline">Timeline · {cursor} of {events.length}</label>
      <div className="replay-v2__timeline">
        <input id="replay-timeline" type="range" min="0" max={events.length} value={cursor}
          onChange={(event) => { setPlaying(false); setCursor(Number(event.target.value)) }}
          aria-label="Replay event cursor" />
        <div className="replay-v2__markers" aria-label="Event markers">
          {events.map((event, index) => {
            const type = event.type || 'event'
            const title = `${type} · ${event.actor || 'system'}`
            return (
              <button type="button" key={`${event.ts}-${index}`} title={title} aria-label={`Jump to ${title}`}
                style={{ left: `${((index + 1) / maxIndex) * 100}%`, backgroundColor: eventColor(type) }}
                onClick={() => { setPlaying(false); setCursor(index + 1) }} />
            )
          })}
        </div>
      </div>
      <div className="replay-v2__legend">
        <span><i style={{ backgroundColor: EVENT_COLORS.offer }} />Offer / quote</span>
        <span><i style={{ backgroundColor: EVENT_COLORS.counter }} />Counter</span>
        <span><i style={{ backgroundColor: EVENT_COLORS.decision }} />Decision</span>
        <span><i style={{ backgroundColor: EVENT_COLORS.phase }} />Other event</span>
      </div>

      <div className="replay-v2__chart">
        <div><strong>Observed prices</strong><span>{chart.latest ? `Latest · ${inr(chart.latest.price)}` : 'No quote visible at this point'}</span></div>
        {chart.points.length ? (
          <svg viewBox="0 0 600 100" role="img" aria-label="Observed offer prices through the replay cursor">
            <line x1={cursorX} y1="8" x2={cursorX} y2="91" stroke="#512672" strokeDasharray="4 4" />
            {chart.points.length > 1 ? <polyline points={points} fill="none" stroke="#12634d" strokeWidth="3" /> : null}
            {chart.points.map((point) => {
              const x = 26 + (point.index / maxIndex) * 548
              const spread = chart.max - chart.min
              const y = spread === 0 ? 50 : 88 - ((point.price - chart.min) / spread) * 70
              return <circle key={point.index} cx={x} cy={y} r="4" fill="#12634d" />
            })}
          </svg>
        ) : <p>No server-provided offer price is available at this cursor.</p>}
      </div>
    </section>
  )
}
