import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import AppShell from './AppShell.jsx'
import { useSession } from '../state/session.js'
import { voice } from '../lib/voice.js'
import { inr } from '../lib/format.js'
import { DESIGN_FLAGS } from '../design/flags.js'
import RoomInsights from '../design/RoomInsights.jsx'
import { selectRoomModel } from '../design/selectors.js'

const ease = [0.22, 1, 0.36, 1]

function PriceTicker({ value, unit, label }) {

  return (
    <div>
      <p className="ticker__label">{label}</p>
      <div className="ticker">
        <span className="ticker__value">{inr(value)}</span>
        <span className="ticker__unit">{unit}</span>
      </div>
    </div>
  )
}

export default function NegotiationRoom() {
  const orb = useSession((s) => s.orb)
  const level = useSession((s) => s.level)
  const negotiation = useSession((s) => s.negotiation)
  const vendors = useSession((s) => s.vendors)
  const firstQuote = useSession((s) => s.firstQuote)
  const lines = useSession((s) => s.lines)
  const community = useSession((s) => s.community)
  const language = useSession((s) => s.language)
  const phase = useSession((s) => s.phase)
  const control = useSession((s) => s.control)
  const paused = control?.action === 'paused'
  const negotiating = Boolean(negotiation) && phase === 'negotiation'

  const vendorList = Object.values(vendors).sort(
    (a, b) => (a.quote?.unit_price ?? 999) - (b.quote?.unit_price ?? 999),
  )
  const bestOffer = selectRoomModel(useSession.getState()).best
  const livePrice = selectRoomModel(useSession.getState()).currentPrice
  const bestVendor = vendorList.find((vendor) => vendor.vendor_id === bestOffer?.vendor_id)

  const lastLine = lines[lines.length - 1]
  const vendorSpeaking = orb === 'speaking' && lastLine?.role === 'vendor'
  const agentSpeaking = orb === 'speaking' && lastLine?.role === 'agent'

  const maxRounds = negotiation?.maxRounds || 3
  const stateLabel = (negotiation?.state || 'Waiting').replaceAll('_', ' ').toLowerCase()

  useEffect(() => {
    if (!negotiation && useSession.getState().status === 'idle') {
      // Deep link: open a session so the room is not dead.
      voice.startLive(language)
    }
  }, [negotiation, language])

  return (
    <AppShell orb={orb} level={level}>
      <header className="panel__head">
        <div>
          <p className="eyebrow">
            {community?.name} · {community?.households} households
          </p>
          <h2 className="panel__title">Negotiation room</h2>
        </div>
        <div className="panel__meta">
          <span className="pill pill--warn">Simulated vendor</span>
          <span className="pill">
            Round {negotiation?.round ?? 0} / {maxRounds}
          </span>
          <span className="pill">{stateLabel}</span>
        </div>
      </header>

      <div className="panel__body">
        {!negotiation ? (
          <div className="room__empty">
            <p>
              No live negotiation yet. Start one from the voice console — ask for water cans in
              Kannada, Hindi or English — or run the guided demo to watch simulated suppliers bid
              for the same verified weekly demand.
            </p>
            <div className="approval-actions" style={{ marginTop: 16 }}>
              <button type="button" className="btn-solid" onClick={() => voice.startDemo(language)}>
                Start guided negotiation
              </button>
              <Link to="/console" className="btn-outline">
                Voice console
              </Link>
            </div>
          </div>
        ) : (
          <>
            {DESIGN_FLAGS.room ? <RoomInsights state={useSession.getState()} /> : null}
            <div className="room__summary">
              {livePrice != null || firstQuote != null ? <PriceTicker
                value={livePrice ?? firstQuote}
                unit={`per ${negotiation.product || 'unit'}`}
                label="Best live quote"
              /> : <p className="ticker__label">Waiting for the first quote…</p>}
              <div className="room__delta">
                {firstQuote != null ? (
                  <>
                    Opening quote <strong>{inr(firstQuote)}</strong>
                  </>
                ) : (
                  <span>Waiting for the first quote…</span>
                )}
              </div>
            </div>

            <div className="vendor-grid">
              {vendorList.map((vendor) => {
                const isBest = bestOffer?.vendor_id === vendor.vendor_id
                const quote = vendor.quote || {}
                return (
                  <motion.article
                    key={vendor.vendor_id}
                    className={`vendor-card ${isBest ? 'is-best' : ''} ${vendorSpeaking && vendor.name === lastLine?.vendor ? 'is-speaking' : ''}`}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, ease }}
                  >
                    <div className="vendor-card__head">
                      <div>
                        <p className="vendor-card__name">{vendor.name}</p>
                        <p className="vendor-card__persona">{vendor.persona}</p>
                      </div>
                      {isBest ? <span className="pill">Best</span> : null}
                    </div>

                    <p className="vendor-card__price">
                      {quote.unit_price != null ? `₹${quote.unit_price}` : '—'}
                      <small>/ {negotiation.unit || 'unit'}</small>
                    </p>

                    <div className="round-dots" aria-label={`${vendor.round || 0} quotes so far`}>
                      {Array.from({ length: maxRounds }).map((_, i) => (
                        <span key={i} className={i < (vendor.round || 0) ? 'is-on' : ''} />
                      ))}
                    </div>

                    <div className="vendor-card__meta">
                      <span>
                        Delivery:{' '}
                        {quote.delivery_charge == null ? '—' : quote.delivery_charge === 0 ? 'free' : `${inr(quote.delivery_charge)} / order`}
                        {vendor.delivery_days ? ` · ${vendor.delivery_days} ${vendor.delivery_days === 1 ? 'day' : 'days'}` : ''}
                      </span>
                      <span>
                        Min qty: {quote.min_qty ?? negotiation.qty ?? '—'} · valid{' '}
                        {quote.valid_days == null ? '—' : `${quote.valid_days} ${quote.valid_days === 1 ? 'day' : 'days'}`}
                      </span>
                    </div>

                    {vendor.line ? <p className="vendor-card__quote">“{vendor.line}”</p> : null}
                  </motion.article>
                )
              })}
            </div>
          </>
        )}
      </div>

      <div className="panel__foot">
        <div className="room__controls">
          <button
            type="button"
            className="btn-outline btn-outline--ink"
            onClick={() => (paused ? voice.resume() : voice.pause())}
            disabled={!negotiating}
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            type="button"
            className="btn-outline btn-outline--ink"
            onClick={() => voice.skip()}
            disabled={!negotiating}
          >
            Skip supplier
          </button>
          <button
            type="button"
            className="btn-outline btn-outline--ink"
            onClick={() => voice.stop()}
            disabled={!negotiating}
          >
            Stop
          </button>
          <span className="pill">{paused ? 'Paused' : negotiating ? 'Playing' : phase}</span>
        </div>
        <div className="speakers">
          <span className={`speaker ${agentSpeaking ? 'is-on' : ''}`}>
            <span className={`mini-orb ${orb === 'speaking' ? 'is-speaking' : ''}`} />
            NegoAI
          </span>
          <span className={`speaker ${vendorSpeaking ? 'is-on' : ''}`}>
            <span className={`mini-orb ${vendorSpeaking ? 'is-speaking' : ''}`} />
            Vendor
          </span>
          {bestVendor && (bestOffer?.unit_price ?? bestVendor.quote?.unit_price) != null ? (
            <span className="speaker" style={{ marginLeft: 'auto', color: '#fff' }}>
              Eligible: {bestVendor.name} at ₹{bestOffer?.unit_price ?? bestVendor.quote?.unit_price}
            </span>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
