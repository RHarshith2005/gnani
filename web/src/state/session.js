import { create } from 'zustand'

export const LANGUAGES = [
  { id: 'kn-IN', label: 'ಕನ್ನಡ', name: 'Kannada', short: 'KN' },
  { id: 'hi-IN', label: 'हिन्दी', name: 'Hindi', short: 'HI' },
  { id: 'en-IN', label: 'English', name: 'English', short: 'EN' },
]

let lineSeq = 0

const initial = {
  status: 'idle', // idle | connecting | ready | error
  mode: 'live',
  sessionId: null,
  community: { id: 'green-residency', name: 'Green Residency', households: 120 },
  capabilities: { stt: 'browser', tts: 'browser' },
  language: 'kn-IN',
  orb: 'idle',
  level: 0,
  speaking: false,
  phase: 'intake',
  lines: [],
  partial: '',
  confirm: null,
  demand: null,
  negotiation: null,
  vendors: {},
  offers: [],
  firstQuote: null,
  admin: null,
  approval: null,
  control: null,
  demandSaved: [],
  notices: [],
  error: null,
  micOn: false,
  demoRunning: false,
}

const MAX_LINES = 80

function pushLine(lines, line) {
  const next = [...lines, { id: ++lineSeq, ts: Date.now(), ...line }]
  return next.slice(-MAX_LINES)
}

export const useSession = create((set) => ({
  ...initial,

  setStatus: (status) => set({ status }),
  setLanguage: (language) => set({ language }),
  setMicOn: (micOn) => set({ micOn }),
  setOrb: (orb) => set({ orb, speaking: orb === 'speaking' }),
  setLevel: (level) => set({ level: Math.max(0, Math.min(1, level)) }),
  setError: (error) => set({ error, status: error ? 'error' : 'idle' }),
  setDemoRunning: (demoRunning) => set({ demoRunning }),
  setPartial: (partial) => set({ partial }),

  addNotice: (notice) =>
    set((s) => ({
      notices: [...s.notices, { id: ++lineSeq, ...notice }].slice(-4),
    })),

  addLine: (line) =>
    set((s) => ({
      lines: pushLine(s.lines, line),
    })),

  reset: () =>
    set((s) => ({
      ...initial,
      mode: s.mode,
      language: s.language,
      status: s.status,
      capabilities: s.capabilities,
      community: s.community,
    })),

  /** Single funnel for every server event. Keeping this exhaustive makes the
   *  gateway protocol the only contract between web and api. */
  applyEvent: (event) => {
    if (!event || typeof event !== 'object') return
    switch (event.type) {
      case 'ready':
        set({
          status: 'ready',
          sessionId: event.session_id,
          mode: event.mode || 'live',
          language: event.language || 'kn-IN',
          community: event.community || initial.community,
          capabilities: event.capabilities || initial.capabilities,
          error: null,
        })
        break
      case 'state':
        set({ orb: event.orb, speaking: event.orb === 'speaking' })
        break
      case 'level':
        set({ level: Math.max(0, Math.min(1, Number(event.value) || 0)) })
        break
      case 'partial':
        set({ partial: event.text || '' })
        break
      case 'transcript':
        set((s) => ({
          lines: pushLine(s.lines, {
            role: event.role || 'system',
            text: event.text,
            subtitle: event.subtitle || '',
            lang: event.lang,
          }),
          partial: '',
        }))
        break
      case 'agent': {
        // Vendor speech already arrived as a `vendor` event; this one only
        // carries its audio, so it must not add a second transcript line.
        const isVendor = event.role === 'vendor'
        set((s) => ({
          lines: isVendor
            ? s.lines
            : pushLine(s.lines, {
                role: 'agent',
                text: event.text,
                subtitle: event.subtitle || '',
                lang: event.lang,
                tts: event.tts,
              }),
          partial: '',
          orb: 'speaking',
          speaking: true,
        }))
        break
      }
      case 'confirm':
        set({ confirm: { text: event.text, items: event.items || [], id: ++lineSeq } })
        break
      case 'confirm_clear':
        set({ confirm: null })
        break
      case 'demand':
        set({ demand: event.slots })
        break
      case 'phase':
        set({ phase: event.phase })
        break
      case 'negotiation':
        set({ negotiation: event, phase: 'negotiation' })
        break
      case 'vendor': {
        const quote = event.quote || {}
        set((s) => {
          const prev = s.vendors[event.vendor_id] || { rounds: [] }
          const entry = {
            ...prev,
            vendor_id: event.vendor_id,
            name: event.vendor_name || prev.name,
            persona: event.persona || prev.persona,
            line: event.line,
            subtitle: event.subtitle,
            round: event.round,
            delivery_days: event.delivery_days || prev.delivery_days,
            quote,
            eligible: Boolean(event.eligible),
            speaking: false,
            rounds: [...prev.rounds, { round: event.round, ...quote }],
          }
          return { vendors: { ...s.vendors, [event.vendor_id]: entry } }
        })
        if (event.line) {
          set((s) => ({
            lines: pushLine(s.lines, {
              role: 'vendor',
              text: event.line,
              subtitle: event.subtitle || '',
              lang: event.lang,
              vendor: event.vendor_name,
            }),
          }))
        }
        break
      }
      case 'offers':
        set((s) => ({
          offers: event.offers || [],
          firstQuote: event.first_quote ?? s.firstQuote,
        }))
        break
      case 'admin':
        set({ admin: event, phase: 'approval' })
        break
      case 'approval':
        set({ approval: event, phase: 'done' })
        break
      case 'control':
        set({ control: { action: event.action, ts: Date.now() } })
        break
      case 'demand_saved':
        set((s) => ({
          demandSaved: [
            ...s.demandSaved,
            {
              id: ++lineSeq,
              product: event.product,
              qty: event.qty,
              frequency: event.frequency,
              delivery_day: event.delivery_day,
              language: event.language,
            },
          ].slice(-6),
        }))
        break
      case 'notice':
        set((s) => ({
          notices: [...s.notices, { id: ++lineSeq, text: event.text, level: event.level || 'info' }].slice(-4),
        }))
        break
      case 'error':
        set({ error: event.message || 'Something went wrong', status: 'error' })
        break
      default:
        break
    }
  },
}))

/** Derived selector: newest line brightest, older lines fade out. */
export function selectLines(state) {
  return state.lines
}
