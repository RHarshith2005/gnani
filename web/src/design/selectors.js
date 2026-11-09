export function selectRoomModel(state) {
  const vendors = Object.values(state.vendors || {})
  const lastLine = state.lines?.at(-1)
  const best = state.offers?.find((offer) => offer.vendor_id === state.admin?.best?.vendor_id) ||
    state.offers?.reduce(
      (current, offer) => (!current || offer.effective < current.effective ? offer : current),
      null,
    )
  const activeVendor = state.orb === 'speaking' && lastLine?.role === 'vendor'
    ? vendors.find((vendor) => vendor.name === lastLine.vendor) || null
    : null
  const currentPrice = vendors.reduce((lowest, vendor) => {
    const price = vendor.quote?.unit_price
    return typeof price === 'number' && (lowest == null || price < lowest) ? price : lowest
  }, null)
  return {
    vendors,
    best,
    activeVendor,
    currentPrice,
    speaker: state.orb !== 'speaking'
      ? null
      : activeVendor
        ? 'vendor'
        : lastLine?.role === 'agent'
          ? 'agent'
          : null,
    latestLine: lastLine || null,
  }
}

export function selectVendorStatus(vendor, negotiation, activeVendor) {
  if (!vendor) return { status: 'queued', label: 'Queued' }
  if (activeVendor?.vendor_id === vendor.vendor_id) return { status: 'calling', label: 'Calling' }
  const count = vendor.rounds?.length || 0
  if (negotiation?.finished || /ESCALATE|WALK_AWAY|FINAL/.test(negotiation?.state || '')) {
    return { status: 'final', label: 'Final' }
  }
  if (count > 1) return { status: 'countered', label: 'Countered' }
  return { status: 'quoted', label: count ? 'Quoted' : 'Queued' }
}

export function selectApprovalOffers(state) {
  return (state.offers || []).map((offer) => ({
    ...offer,
    recommended: offer.vendor_id === state.admin?.best?.vendor_id,
  }))
}
