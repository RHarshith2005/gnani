import test from 'node:test'
import assert from 'node:assert/strict'
import { clamp, inr, pct } from './format.js'

test('rupee formatting uses Indian grouping', () => {
  assert.equal(inr(1440), '₹1,440')
  assert.equal(inr(6840), '₹6,840')
  assert.equal(inr(undefined), '—')
})

test('percent and clamp stay in range', () => {
  assert.equal(pct(0.144), '14%')
  assert.equal(clamp(1.4), 1)
  assert.equal(clamp(-0.2), 0)
  assert.equal(clamp(0.4, 0.2, 0.8), 0.4)
})
