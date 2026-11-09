import test from 'node:test'
import assert from 'node:assert/strict'
import { useSession } from './session.js'

function reset() {
  useSession.getState().reset()
  useSession.setState({ lines: [], vendors: {}, notices: [] })
}

test('ready event stores session, language and capabilities', () => {
  reset()
  useSession.getState().applyEvent({
    type: 'ready',
    session_id: 'session-test',
    mode: 'live',
    language: 'kn-IN',
    capabilities: { stt: 'gnani', tts: 'gnani' },
  })
  const state = useSession.getState()
  assert.equal(state.status, 'ready')
  assert.equal(state.sessionId, 'session-test')
  assert.equal(state.language, 'kn-IN')
  assert.equal(state.capabilities.stt, 'gnani')
})

test('vendor line is stored once, and its audio agent event adds no duplicate', () => {
  reset()
  useSession.getState().applyEvent({
    type: 'vendor',
    vendor_id: 'vendor-friendly',
    vendor_name: 'Bengaluru Aqua Distributors',
    line: 'Nineteen rupees per can.',
    quote: { unit_price: 19 },
    round: 2,
    eligible: true,
  })
  const afterVendor = useSession.getState().lines.length
  assert.equal(afterVendor, 1)
  assert.equal(useSession.getState().vendors['vendor-friendly'].quote.unit_price, 19)

  useSession.getState().applyEvent({
    type: 'agent',
    role: 'vendor',
    text: 'Nineteen rupees per can.',
  })
  assert.equal(useSession.getState().lines.length, afterVendor)
})

test('confirm, admin and rejection drive the phases', () => {
  reset()
  useSession.getState().applyEvent({ type: 'confirm', text: 'Three water cans — correct?', items: [] })
  assert.match(useSession.getState().confirm.text, /correct/)

  useSession.getState().applyEvent({ type: 'admin', total_qty: 360, savings: 1440 })
  assert.equal(useSession.getState().phase, 'approval')
  assert.equal(useSession.getState().admin.savings, 1440)

  useSession.getState().applyEvent({ type: 'approval', decision: 'rejected' })
  assert.equal(useSession.getState().phase, 'done')
})

test('offers keep the best-first ordering and first quote', () => {
  reset()
  useSession.getState().applyEvent({
    type: 'offers',
    offers: [{ unit_price: 19, effective: 6840 }],
    first_quote: 22,
  })
  assert.equal(useSession.getState().offers[0].unit_price, 19)
  assert.equal(useSession.getState().firstQuote, 22)
})
