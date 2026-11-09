import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { inr } from '../lib/format.js'
import { DESIGN_FLAGS } from './flags.js'
import { selectApprovalOffers } from './selectors.js'
import './design.css'

const API = import.meta.env.VITE_API_URL || ''

function OfferBoard({ offers, risks }) {
  return (
    <section className="design-card approval-board">
      <div className="design-card__head">
        <div><p className="design-kicker">Offer comparison</p><h3>Choose with the whole picture</h3></div>
        <span className="design-note">Weekly costs and terms from vendor offers</span>
      </div>
      <div className="offer-grid">
        {offers.map((offer) => (
          <article className={`offer-card ${offer.recommended ? 'offer-card--recommended' : ''}`} key={offer.vendor_id}>
            {offer.recommended ? <span className="offer-card__badge">Recommended</span> : null}
            <h4>{offer.vendor_name}</h4>
            <p className="offer-card__source">Simulated vendor</p>
            <p className="offer-card__cost">{inr(offer.effective)}<small> / week</small></p>
            <dl>
              <div><dt>Unit price</dt><dd>{inr(offer.unit_price)}</dd></div>
              <div><dt>Delivery</dt><dd>{offer.delivery_charge == null ? '—' : offer.delivery_charge === 0 ? 'Free' : inr(offer.delivery_charge)}{offer.delivery_days ? ` · ${offer.delivery_days} ${offer.delivery_days === 1 ? 'day' : 'days'}` : ''}</dd></div>
              <div><dt>Minimum quantity</dt><dd>{offer.min_qty ?? '—'}</dd></div>
              <div><dt>Valid</dt><dd>{offer.valid_days == null ? '—' : `${offer.valid_days} ${offer.valid_days === 1 ? 'day' : 'days'}`}</dd></div>
            </dl>
          </article>
        ))}
        {!offers.length ? <p className="design-note">Offers will appear here when the negotiation is complete.</p> : null}
      </div>
      {risks.length ? (
        <div className="risk-chips" aria-label="Risks to consider">
          {risks.map((risk) => <span key={risk}>{risk}</span>)}
        </div>
      ) : null}
    </section>
  )
}

function ApprovalParticles({ active }) {
  const reduceMotion = useReducedMotion()
  if (!active) return null
  return (
    <svg className="approval-burst" viewBox="0 0 220 140" aria-hidden="true">
      {Array.from({ length: 14 }, (_, index) => {
        const angle = (Math.PI * 2 * index) / 14
        const x = Math.cos(angle) * 70
        const y = Math.sin(angle) * 48
        return (
          <motion.circle key={index} cx="110" cy="70" r={index % 3 + 2} fill={index % 2 ? '#f5b932' : '#2d725c'}
            initial={{ opacity: 1, x: 0, y: 0, scale: 0.6 }}
            animate={{ opacity: 0, x: reduceMotion ? 0 : x, y: reduceMotion ? 0 : y, scale: 1 }}
            transition={{ duration: reduceMotion ? 0 : 0.8, ease: 'easeOut' }} />
        )
      })}
    </svg>
  )
}

function SlideToApprove({ onApprove }) {
  const [value, setValue] = useState(0)
  const [armed, setArmed] = useState(false)
  return (
    <div className="slide-approve">
      <label htmlFor="approval-slider">Slide to approve <span>Keyboard: use arrow keys, then confirm</span></label>
      <input id="approval-slider" type="range" min="0" max="100" step="1" value={value}
        aria-valuetext={armed ? 'Ready to confirm approval' : `${value} percent`}
        onChange={(event) => {
          const next = Number(event.target.value)
          setValue(next)
          setArmed(next === 100)
        }} />
      <button type="button" className="btn-solid" disabled={!armed}
        onClick={() => { onApprove(); setValue(0); setArmed(false) }}>
        Confirm approval
      </button>
    </div>
  )
}

function TrustStrip({ receipt }) {
  return (
    <section className="trust-strip" aria-label="Trust and transparency">
      <span>AI disclosed</span>
      <span>Vendors simulated</span>
      <span>Numbers engine-computed</span>
      <span>Agent cannot accept</span>
      <span>Tamper-evident receipt{receipt?.chain_head ? ` · ${String(receipt.chain_head).slice(0, 12)}…` : ''}</span>
    </section>
  )
}

function makePoster(admin, receipt) {
  const canvas = document.createElement('canvas')
  canvas.width = 1080
  canvas.height = 1350
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Canvas is unavailable in this browser.')
  const gradient = context.createLinearGradient(0, 0, 1080, 1350)
  gradient.addColorStop(0, '#eed7fd')
  gradient.addColorStop(1, '#c7a4da')
  context.fillStyle = gradient
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.fillStyle = '#2e1046'
  context.font = '600 30px Poppins, sans-serif'
  context.fillText('NEGOAI · COMMUNITY PROCUREMENT', 82, 116)
  context.font = '500 46px Poppins, sans-serif'
  context.fillText('Savings receipt', 82, 220)
  context.font = '700 96px Oswald, sans-serif'
  context.fillText(inr(admin.savings), 82, 390)
  context.font = '400 28px Poppins, sans-serif'
  context.fillText('weekly savings vs first quote', 82, 448)
  const firstQuote = admin.first_quote
  const bestPrice = admin.best?.unit_price
  if (firstQuote != null && bestPrice != null) {
    context.font = '500 34px Poppins, sans-serif'
    context.fillText(`${inr(firstQuote)} → ${inr(bestPrice)} per ${admin.unit || 'unit'}`, 82, 570)
  }
  context.font = '600 34px Poppins, sans-serif'
  context.fillText(admin.best?.vendor_name || 'No recommended vendor', 82, 710)
  context.font = '400 24px Poppins, sans-serif'
  context.fillText(`Proof · ${String(receipt.chain_head).slice(0, 16)}…`, 82, 810)
  context.fillText(window.location.href.slice(0, 52), 82, 900)
  context.font = '600 24px Poppins, sans-serif'
  context.fillText('Simulated vendors, synthetic data', 82, 1250)
  return canvas
}

export default function ApprovalExperience({ admin, offers, onApprove, sessionId, approval }) {
  const [receipt, setReceipt] = useState(null)
  const [receiptError, setReceiptError] = useState('')
  const [posterError, setPosterError] = useState('')
  const [burst, setBurst] = useState(false)
  const stageRef = useRef(null)
  useEffect(() => {
    if (!sessionId) return undefined
    const controller = new AbortController()
    fetch(`${API}/api/sessions/${sessionId}/receipt`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`Receipt unavailable (${response.status})`)))
      .then(setReceipt)
      .catch((error) => {
        if (error.name !== 'AbortError') setReceiptError(error.message)
      })
    return () => controller.abort()
  }, [sessionId])

  if (!DESIGN_FLAGS.approval) return null
  const comparisonOffers = selectApprovalOffers({ offers, admin })
  const approve = () => {
    onApprove()
    setBurst(true)
    window.setTimeout(() => setBurst(false), 900)
    stageRef.current = document.querySelector('.screen__stage')
    stageRef.current?.classList.add('approval-glow')
    window.setTimeout(() => stageRef.current?.classList.remove('approval-glow'), 900)
  }
  const savePoster = () => {
    try {
      if (!receipt?.chain_head) throw new Error('The tamper-evident receipt is not ready yet.')
      const canvas = makePoster(admin, receipt)
      const link = document.createElement('a')
      link.download = 'negoai-savings-receipt.png'
      link.href = canvas.toDataURL('image/png')
      link.click()
      setPosterError('')
    } catch (error) {
      setPosterError(error.message)
    }
  }
  const copySummary = async () => {
    try {
      await navigator.clipboard.writeText(
        `Savings ${inr(admin.savings)} · ${admin.best?.vendor_name || 'No vendor'} · proof ${receipt?.chain_head || ''} · ${window.location.href}`,
      )
      setPosterError('')
    } catch {
      setPosterError('Clipboard access is unavailable.')
    }
  }
  return (
    <div className="approval-experience">
      <OfferBoard offers={comparisonOffers} risks={admin.risks || []} />
      <TrustStrip receipt={receipt} />
      {receiptError ? <p className="design-message">{receiptError}</p> : null}
      <section className="design-card savings-poster">
        <div className="design-card__head"><div><p className="design-kicker">Takeaway</p><h3>Savings receipt poster</h3></div></div>
        <div className="poster-preview">
          <span>NEGOAI · WEEKLY SAVINGS</span>
          <strong>{inr(admin.savings)}</strong>
          <p>{admin.best?.vendor_name || 'No recommended vendor'}</p>
          <small>Simulated vendors, synthetic data</small>
          <small>{receipt?.chain_head ? `Proof ${String(receipt.chain_head).slice(0, 12)}…` : 'Waiting for tamper-evident proof'}</small>
        </div>
        <div className="approval-poster-actions">
          <button type="button" className="btn-outline" onClick={savePoster} disabled={!receipt?.chain_head}>Download PNG</button>
          <button type="button" className="btn-outline" onClick={copySummary}>Copy summary</button>
        </div>
        {posterError ? <p className="design-message" role="status">{posterError}</p> : null}
      </section>
      {!approval ? (
        <div className="slide-wrap">
          <ApprovalParticles active={burst} />
          <SlideToApprove onApprove={approve} />
        </div>
      ) : null}
    </div>
  )
}
