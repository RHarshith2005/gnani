export function inr(value, { decimals = 0 } = {}) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `₹${n.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

export function pct(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${Math.round(n * 100)}%`
}

export function clamp(v, min = 0, max = 1) {
  return Math.max(min, Math.min(max, v))
}

export function classNames(...parts) {
  return parts.filter(Boolean).join(' ')
}

export const ROLE_LABEL = {
  resident: 'Resident',
  agent: 'NegoAI',
  vendor: 'Vendor',
  system: 'System',
}
