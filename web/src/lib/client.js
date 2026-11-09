import { useSession } from '../state/session.js'
import { player } from './audio.js'

function resolveUrl() {
  const explicit = import.meta.env?.VITE_API_URL
  if (explicit) {
    return explicit.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws/voice'
  }
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/voice`
}

/**
 * One socket per tab, one brain per session. The socket carries mic audio,
 * typed text, TTS audio and every UI event — the same contract for all channels.
 */
class VoiceClient {
  constructor() {
    this.ws = null
    this.pending = []
    this.retries = 0
    this.closedByUser = false
    this.sessionStarted = false
    this.pendingHello = false
    this.pingTimer = 0
    this.url = resolveUrl()
  }

  get connected() {
    return this.ws?.readyState === WebSocket.OPEN
  }

  connect() {
    if (this.sessionStarted && !this.pendingHello && !this.ws) return
    if (this.connected || this.ws?.readyState === WebSocket.CONNECTING) return
    this.closedByUser = false
    const store = useSession.getState()
    store.setStatus('connecting')

    let ws
    try {
      ws = new WebSocket(this.url)
    } catch (err) {
      store.setError(`Cannot open voice socket: ${err.message}`)
      return
    }
    this.ws = ws
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      this.retries = 0
      if (this.pendingHello || !this.sessionStarted) {
        const { mode, language } = useSession.getState()
        ws.send(JSON.stringify({ type: 'hello', mode, language }))
        this.pendingHello = false
        this.sessionStarted = true
      }
      this.pending.splice(0).forEach((msg) => this.send(msg))
      clearInterval(this.pingTimer)
      this.pingTimer = setInterval(() => this.send({ type: 'ping' }), 20_000)
    }

    ws.onmessage = (e) => {
      if (this.ws !== ws) return
      if (typeof e.data !== 'string') return
      let payload
      try {
        payload = JSON.parse(e.data)
      } catch {
        return
      }
      useSession.getState().applyEvent(payload)
    }

    ws.onerror = () => {
      useSession.setState({ status: 'error', error: 'Voice gateway unreachable' })
    }

    ws.onclose = () => {
      clearInterval(this.pingTimer)
      this.pingTimer = 0
      this.ws = null
      const store = useSession.getState()
      if (!this.closedByUser && this.sessionStarted) {
        player.stop()
        store.addNotice({ text: 'Connection dropped. Tap to continue.', level: 'warn' })
      }
      if (!this.closedByUser && this.sessionStarted) store.setStatus('idle')
    }
  }

  send(message) {
    if (!this.connected) {
      if (this.sessionStarted && !this.pendingHello) return false
      this.pending.push(message)
      this.connect()
      return false
    }
    this.ws.send(JSON.stringify(message))
    return true
  }

  start(mode = 'live', language = 'kn-IN') {
    useSession.setState({ mode, language })
    if (this.connected) {
      this.send({ type: 'hello', mode, language })
      this.pendingHello = false
      this.sessionStarted = true
    } else {
      this.pendingHello = true
      this.connect()
    }
  }

  resume() {
    this.pendingHello = true
    if (this.connected) {
      const { mode, language } = useSession.getState()
      this.send({ type: 'hello', mode, language })
      this.pendingHello = false
      this.sessionStarted = true
    } else {
      this.connect()
    }
  }

  text(text) {
    this.send({ type: 'text', text })
  }

  audio(int16) {
    const bytes = new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength)
    let binary = ''
    const step = 0x8000
    for (let i = 0; i < bytes.length; i += step) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + step))
    }
    this.send({ type: 'audio', pcm: btoa(binary), sampleRate: 16000 })
  }

  bargeIn() {
    this.send({ type: 'barge_in' })
  }

  playbackDone(utteranceId, epoch) {
    this.send({ type: 'playback_done', utterance_id: utteranceId, epoch })
  }

  control(action) {
    this.send({ type: 'control', action })
  }

  approve(decision, note = '') {
    this.send({ type: 'approve', decision, note })
  }

  reset() {
    this.send({ type: 'reset' })
  }

  close() {
    this.closedByUser = true
    clearInterval(this.pingTimer)
    this.pingTimer = 0
    this.ws?.close()
    this.ws = null
  }
}

export const voiceClient = new VoiceClient()
