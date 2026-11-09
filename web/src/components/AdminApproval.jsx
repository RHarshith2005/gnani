import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import AppShell from './AppShell.jsx'
import { useSession } from '../state/session.js'
import { voice } from '../lib/voice.js'
import { inr } from '../lib/format.js'
import { DESIGN_FLAGS } from '../design/flags.js'
import ApprovalExperience from '../design/ApprovalExperience.jsx'

const ease = [0.22, 1, 0.36, 1]

export default function AdminApproval() {
  const orb = useSession((s) => s.orb)
  const level = useSession((s) => s.level)
  const admin = useSession((s) => s.admin)
  const approval = useSession((s) => s.approval)
  const negotiation = useSession((s) => s.negotiation)
  const offers = useSession((s) => s.offers)
  const sessionId = useSession((s) => s.sessionId)
  const language = useSession((s) => s.language)

  const waiting = !admin

  return (
    <AppShell orb={orb} level={level}>
      <header className="panel__head">
        <div>
          <p className="eyebrow">Community committee</p>
          <h2 className="panel__title">Admin approval</h2>
        </div>
        <div className="panel__meta">
          <span className="pill">Engine-computed numbers</span>
          {negotiation?.product ? <span className="pill">{negotiation.product}</span> : null}
        </div>
      </header>

      <div className="panel__body">
        {waiting ? (
          <div className="admin__empty">
            <p>
              Nothing to approve yet. The engine never accepts an offer — it only marks offers
              eligible when they come in at or below the committee's ceiling. Run a negotiation and
              the summary, savings and risks land here.
            </p>
            <div className="approval-actions" style={{ marginTop: 16 }}>
              <button type="button" className="btn-solid" onClick={() => voice.startDemo(language)}>
                Run guided negotiation
              </button>
              <Link to="/room" className="btn-outline">
                Open negotiation room
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="admin-grid">
              <motion.div
                className="admin-card admin-card--wide admin-card--hero"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, ease }}
              >
                <p className="admin-card__label">Weekly savings vs first quote</p>
                <p className="admin-card__value admin-card__value--big">
                  {inr(admin.savings)}
                </p>
                <p className="admin-card__sub">
                  {admin.first_quote != null && admin.best?.unit_price != null
                    ? `${inr(admin.first_quote)} → ${inr(admin.best.unit_price)} per ${admin.unit || 'unit'} across ${admin.total_qty} units a week`
                    : `Across ${admin.total_qty} units a week`}
                </p>
              </motion.div>

              <motion.div
                className="admin-card"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.05, ease }}
              >
                <p className="admin-card__label">Total verified demand</p>
                <p className="admin-card__value">
                  {admin.total_qty} <small style={{ fontSize: 13 }}>{admin.unit || 'units'} / week</small>
                </p>
                <p className="admin-card__sub">
                  Confirmed by {admin.households} households in {admin.community || 'the society'}, aggregated
                  after each resident confirmed their quantity in words.
                </p>
              </motion.div>

              <motion.div
                className="admin-card"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.1, ease }}
              >
                <p className="admin-card__label">Best eligible offer</p>
                <p className="admin-card__value">
                  {admin.best ? inr(admin.best.unit_price) : '—'}
                  <small style={{ fontSize: 13 }}> / {admin.unit || 'unit'}</small>
                </p>
                <p className="admin-card__sub">
                  {admin.best?.vendor_name || 'No eligible vendor'} ·{' '}
                  {admin.best?.delivery_charge == null
                    ? '— delivery'
                    : admin.best.delivery_charge === 0
                      ? 'free delivery'
                      : `${inr(admin.best.delivery_charge)} delivery`}
                  {admin.best?.delivery_days ? ` in ${admin.best.delivery_days} days` : ''}
                </p>
              </motion.div>

              <div className="admin-card admin-card--wide">
                <p className="admin-card__label">Risks to note before approving</p>
                <ul className="risks">
                  {(admin.risks || []).map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </div>

              {DESIGN_FLAGS.approval ? (
                <ApprovalExperience
                  admin={admin}
                  offers={offers}
                  approval={approval}
                  sessionId={negotiation?.negotiation_id || sessionId}
                  onApprove={() => voice.approve('approved')}
                />
              ) : null}

              <div className="admin-card admin-card--wide">
                <p className="admin-card__label">Summary</p>
                <div className="summary">
                  {admin.summary_en}
                  {admin.summary_kn ? <p className="summary__kn">{admin.summary_kn}</p> : null}
                </div>
              </div>
            </div>

            <div className="approval-actions">
              {approval ? (
                <motion.div
                  className="approval-banner"
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.4, ease }}
                >
                  {approval.decision === 'approved'
                    ? 'Decision recorded. Vendors are simulated.'
                    : 'Decision recorded. Vendors are simulated.'}
                </motion.div>
              ) : (
                <>
                  <button type="button" className="btn-solid" onClick={() => voice.approve('approved')}>
                    Approve offer
                  </button>
                  <button
                    type="button"
                    className="btn-outline"
                    onClick={() => voice.approve('rejected')}
                  >
                    Reject
                  </button>
                  <span className="pill">One approval replaces a group chat</span>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
