import { motion, useReducedMotion } from 'framer-motion'
import { selectRoomModel, selectVendorStatus } from './selectors.js'
import { DESIGN_FLAGS } from './flags.js'
import './design.css'

const SERIES = ['#ffd166', '#9de3d5', '#f4a8d7']

function PriceChart({ vendors, firstQuote, currentPrice, bestVendor }) {
  const reduceMotion = useReducedMotion()
  const values = vendors.flatMap((vendor) =>
    (vendor.rounds || []).map((round) => round.unit_price).filter(Number.isFinite),
  )
  if (Number.isFinite(firstQuote)) values.push(firstQuote)
  if (!values.length) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (round, count) => 38 + (round - 1) * (284 / Math.max(1, count - 1))
  const y = (price) => 126 - ((price - min) / span) * 92
  return (
    <section className="design-card room-chart" aria-label="Vendor price descent chart">
      <div className="design-card__head">
        <div><p className="design-kicker">Live price movement</p><h3>Every round, in view</h3></div>
        <span className="design-note">{bestVendor && currentPrice != null ? `Current best · ${bestVendor.name} · ${currentPrice}` : 'Price per unit · server quotes'}</span>
      </div>
      <svg viewBox="0 0 360 160" role="img" aria-label="Price by negotiation round">
        {Number.isFinite(firstQuote) ? (
          <>
            <line x1="38" x2="322" y1={y(firstQuote)} y2={y(firstQuote)} className="chart-baseline" />
            <text x="38" y={Math.max(14, y(firstQuote) - 7)} className="chart-baseline-label">Opening quote</text>
          </>
        ) : null}
        {[1, 2, 3].map((round) => (
          <g key={round}>
            <line x1={x(round, 3)} x2={x(round, 3)} y1="30" y2="130" className="chart-grid" />
            <text x={x(round, 3)} y="151" textAnchor="middle" className="chart-axis">Round {round}</text>
          </g>
        ))}
        {vendors.map((vendor, index) => {
          const points = (vendor.rounds || []).filter((round) => Number.isFinite(round.unit_price))
          if (!points.length) return null
          const coordinates = points.map((point) => `${x(point.round, 3)},${y(point.unit_price)}`).join(' ')
          return (
            <g key={vendor.vendor_id} className="chart-series">
              <motion.polyline
                points={coordinates}
                fill="none"
                stroke={SERIES[index % SERIES.length]}
                strokeWidth="3"
                strokeLinecap="square"
                initial={reduceMotion ? false : { pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.9, ease: 'easeOut' }}
              />
              {points.map((point) => (
                <circle key={`${point.round}-${point.unit_price}`} cx={x(point.round, 3)} cy={y(point.unit_price)} r="4" fill={SERIES[index % SERIES.length]}>
                  <title>{vendor.name}: {point.unit_price} per unit, round {point.round}</title>
                </circle>
              ))}
            </g>
          )
        })}
      </svg>
      <div className="chart-legend">
        {vendors.map((vendor, index) => (
          <span key={vendor.vendor_id}><i style={{ background: SERIES[index % SERIES.length] }} />{vendor.name} <strong>Simulated</strong></span>
        ))}
      </div>
    </section>
  )
}

function ProgressRail({ negotiation, vendors, activeVendor }) {
  const nodes = Array.from({ length: 3 }, (_, index) => vendors[index] || null)
  return (
    <section className="design-card">
      <div className="design-card__head"><div><p className="design-kicker">Call progress</p><h3>One supplier at a time</h3></div></div>
      <ol className="call-rail">
        {nodes.map((vendor, index) => {
          const item = selectVendorStatus(vendor, negotiation, activeVendor)
          return (
            <li key={vendor?.vendor_id || `queued-${index}`} className={`call-rail__node is-${item.status}`}>
              <span className="call-rail__marker">{String(index + 1).padStart(2, '0')}</span>
              <span className="call-rail__copy">
                <strong>{vendor?.name || `Supplier ${index + 1}`}</strong>
                <small>{item.label} · Simulated</small>
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

function SpeakerClarity({ model }) {
  const speaker = model.speaker || 'agent'
  return (
    <div className={`speaker-focus speaker-focus--${speaker}`} aria-label={`Current speaker: ${speaker === 'vendor' ? model.activeVendor?.name : 'NegoAI'}`}>
      <div className="speaker-focus__avatar" aria-hidden="true">{speaker === 'vendor' ? 'V' : 'N'}</div>
      <div><strong>{speaker === 'vendor' ? model.activeVendor?.name || 'Simulated vendor' : 'NegoAI'}</strong><small>{speaker === 'vendor' ? 'Simulated vendor' : 'AI negotiator'}</small></div>
      <div className="voice-wave" aria-hidden="true">{[8, 15, 23, 12, 19, 7, 17, 10, 22, 12, 6].map((height, index) => <i key={index} style={{ '--wave-height': `${height}px` }} />)}</div>
    </div>
  )
}

function LiveCaption({ line, partial }) {
  if (!line && !partial) return null
  return (
    <div className="live-caption" aria-live="polite">
      <span className="live-caption__label">{partial ? 'You · live transcript' : line?.role === 'vendor' ? 'Simulated vendor' : 'NegoAI'}</span>
      <p lang={line?.lang}>{partial || line?.text}</p>
      {line?.subtitle && line.subtitle !== line.text ? <small>{line.subtitle}</small> : null}
    </div>
  )
}

export default function RoomInsights({ state }) {
  if (!DESIGN_FLAGS.room) return null
  const model = selectRoomModel(state)
  return (
    <div className="room-insights">
      <SpeakerClarity model={model} />
      <LiveCaption line={model.latestLine} partial={state.partial} />
      <PriceChart vendors={model.vendors} firstQuote={state.firstQuote} currentPrice={model.currentPrice} bestVendor={model.best} />
      <ProgressRail negotiation={state.negotiation} vendors={model.vendors} activeVendor={model.activeVendor} />
    </div>
  )
}
