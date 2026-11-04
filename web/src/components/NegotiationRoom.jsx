import { useEffect, useState } from 'react'
import { animate, motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import AppShell from './AppShell.jsx'
import { useSession } from '../state/session.js'
import { voice } from '../lib/voice.js'
import { inr } from '../lib/format.js'

const ease = [0.22, 1, 0.36, 1]

function PriceTicker({ value, unit, label }) {
  const [display, setDisplay] = useState(value ?? 0)

  useEffect(() => {
    if (value == null) return
    const controls = animate(display, value, {
      duration: 0.7,
      ease,
      onUpdate: (v) => setDisplay(v),
    })
    return () => controls.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return (
    <div>
      <p className="ticker__label">{label}</p>
      <div className="ticker">
        <span className="ticker__value">₹{Math.round(display)}</span>
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
  const offers = useSession((s) => s.offers)
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
  const bestOffer = offers.length
    ? offers.reduce((best, offer) => (offer.effective < best.effective ? offer : best), offers[0])
    : null
  const bestVendor = bestOffer ? vendors[bestOffer.vendor_id] : null
  const livePrice = vendorList.length
    ? Math.min(...vendorList.map((v) => v.quote?.unit_price ?? Infinity))
    : null

  const lastLine = lines[lines.length - 1]
  const agentSpeaking = orb === 'speaking' || orb === 'listening' || orb === 'thinking'
  const vendorSpeaking = lastLine?.role === 'vendor' && orb !== 'speaking'

  const maxRounds = negotiation?.maxRounds || 3
  const savings =
    firstQuote != null && livePrice != null
      ? Math.max(0, (firstQuote - livePrice) * (negotiation?.qty || 360))
      : null

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
          <span className="pill">{negotiation?.state || 'Waiting'}</span>
        </div>
      </header>

      <div className="panel__body">
        {!negotiation ? (
          <div className="room__empty">
            <p>
              No live negotiation yet. Start one from the voice console — ask for water cans in
              Kannada, Hindi or English — or run the guided demo to watch three simulated suppliers
              bid for the same 360-can weekly demand.
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
            <div className="room__summary">
              <PriceTicker
                value={livePrice ?? firstQuote ?? 0}
                unit={`per ${negotiation.product || 'unit'}`}
                label="Best live quote"
              />
              <div className="room__delta">
                {firstQuote != null ? (
                  <>
                    Opening quote <strong>{inr(firstQuote)}</strong>
                    {savings ? (
                      <span>
                        {inr(savings)} saved per week at this price
                      </span>
                    ) : null}
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
                    className={`vendor-card ${isBest ? 'is-best' : ''} ${vendorSpeaking && vendor.vendor_id === lastLine?.vendor ? 'is-speaking' : ''}`}
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
                        {quote.delivery_charge ? `${inr(quote.delivery_charge)} / order` : 'free'}
                        {vendor.delivery_days ? ` · ${vendor.delivery_days} days` : ''}
                      </span>
                      <span>
                        Min qty: {quote.min_qty ?? negotiation.qty ?? '—'} · valid{' '}
                        {quote.valid_days ?? 7} days
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
          {bestVendor ? (
            <span className="speaker" style={{ marginLeft: 'auto', color: '#fff' }}>
              Eligible: {bestVendor.name} at ₹{bestVendor.quote?.unit_price}
            </span>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
