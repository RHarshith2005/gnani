/**
 * Audio plumbing. Three transports, one contract for the UI:
 *   1. Mic -> AudioWorklet -> 16 kHz PCM16 -> WebSocket (Gnani Prisma path)
 *   2. Gnani Timbre PCM -> Web Audio queue (server path)
 *   3. Browser SpeechSynthesis / SpeechRecognition (zero-key fallback so the
 *      demo always runs, even before the Gnani key lands on the box)
 */
import { useSession } from '../state/session.js'

const TARGET_RATE = 16000

export function bytesToBase64(int16) {
  const bytes = new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength)
  let binary = ''
  const step = 0x8000
  for (let i = 0; i < bytes.length; i += step) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + step))
  }
  return btoa(binary)
}

export function base64ToInt16(b64) {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Int16Array(bytes.buffer, 0, Math.floor(bytes.length / 2))
}

export function rms(int16) {
  if (!int16.length) return 0
  let sum = 0
  for (let i = 0; i < int16.length; i++) {
    const v = int16[i] / 32768
    sum += v * v
  }
  return Math.sqrt(sum / int16.length)
}

/* -------------------------------------------------------------------------- */
/* Capture                                                                    */
/* -------------------------------------------------------------------------- */

export async function createMic({ onChunk }) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('Microphone API unavailable in this browser')
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  })

  const AudioCtx = window.AudioContext || window.webkitAudioContext
  const ctx = new AudioCtx()
  await ctx.audioWorklet.addModule('/worklets/pcm-worklet.js')

  const source = ctx.createMediaStreamSource(stream)
  const worklet = new AudioWorkletNode(ctx, 'negoai-pcm', {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    outputChannelCount: [1],
    processorOptions: { targetRate: TARGET_RATE, frameMs: 50 },
  })

  // Keep the graph alive without echoing the mic to the speakers.
  const sink = ctx.createGain()
  sink.gain.value = 0

  const analyser = ctx.createAnalyser()
  analyser.fftSize = 512
  analyser.smoothingTimeConstant = 0.75

  source.connect(analyser)
  source.connect(worklet)
  worklet.connect(sink)
  sink.connect(ctx.destination)

  let raf = 0
  const spectrum = new Uint8Array(analyser.frequencyBinCount)
  const pump = () => {
    analyser.getByteFrequencyData(spectrum)
    let sum = 0
    for (let i = 0; i < spectrum.length; i++) sum += spectrum[i]
    const lvl = Math.min(1, sum / spectrum.length / 140)
    useSession.getState().setLevel(lvl)
    raf = requestAnimationFrame(pump)
  }
  pump()

  worklet.port.onmessage = (e) => onChunk?.(e.data)

  return {
    stop() {
      cancelAnimationFrame(raf)
      worklet.port.onmessage = null
      try {
        worklet.disconnect()
        source.disconnect()
        sink.disconnect()
      } catch {
        /* already torn down */
      }
      stream.getTracks().forEach((t) => t.stop())
      ctx.close().catch(() => {})
    },
  }
}

/* -------------------------------------------------------------------------- */
/* Playback                                                                   */
/* -------------------------------------------------------------------------- */

export class AudioPlayer {
  constructor() {
    this.ctx = null
    this.gain = null
    this.analyser = null
    this.queue = []
    this.playing = false
    this.enabled = true
    this.silentUntil = 0
    this.lastLevel = 0
    this.spectrum = null
    this.raf = 0
    this.onIdle = null
  }

  async unlock() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext
      if (!AudioCtx) return
      this.ctx = new AudioCtx()
      this.gain = this.ctx.createGain()
      this.gain.gain.value = 1
      this.analyser = this.ctx.createAnalyser()
      this.analyser.fftSize = 512
      this.analyser.smoothingTimeConstant = 0.7
      this.gain.connect(this.analyser)
      this.analyser.connect(this.ctx.destination)
      this.spectrum = new Uint8Array(this.analyser.frequencyBinCount)
    }
    if (this.ctx.state === 'suspended') await this.ctx.resume()
    this.startLevelLoop()
  }

  startLevelLoop() {
    cancelAnimationFrame(this.raf)
    const loop = () => {
      if (this.analyser && this.spectrum) {
        this.analyser.getByteFrequencyData(this.spectrum)
        let sum = 0
        for (let i = 0; i < this.spectrum.length; i++) sum += this.spectrum[i]
        const lvl = Math.min(1, sum / this.spectrum.length / 150)
        this.lastLevel = lvl
        const store = useSession.getState()
        if (store.orb === 'speaking' && lvl > 0.02) store.setLevel(lvl)
      }
      this.raf = requestAnimationFrame(loop)
    }
    loop()
  }

  /** Enqueue an Int16 PCM chunk at 16 kHz. */
  push(int16, sampleRate = TARGET_RATE) {
    if (!this.ctx || !this.enabled) return
    const floats = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) floats[i] = int16[i] / 32768

    const buffer = this.ctx.createBuffer(1, floats.length, sampleRate)
    buffer.copyToChannel(floats, 0)

    const src = this.ctx.createBufferSource()
    src.buffer = buffer
    src.connect(this.gain)

    const startAt = Math.max(this.ctx.currentTime + 0.01, this.silentUntil)
    src.start(startAt)
    this.silentUntil = startAt + buffer.duration
    this.queue.push(src)
    src.onended = () => {
      this.queue = this.queue.filter((s) => s !== src)
      if (this.queue.length === 0) this.onIdle?.()
    }
  }

  pause() {
    if (this.ctx && this.ctx.state === 'running') {
      this.ctx.suspend().catch(() => {})
    }
    if (window.speechSynthesis?.speaking) window.speechSynthesis.pause()
  }

  resume() {
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {})
    }
    if (window.speechSynthesis?.paused) window.speechSynthesis.resume()
  }

  stop() {
    this.queue.forEach((src) => {
      try {
        src.stop()
      } catch {
        /* already stopped */
      }
    })
    this.queue = []
    this.silentUntil = this.ctx?.currentTime || 0
    if (this.ctx) window.speechSynthesis?.cancel()
  }

  get speaking() {
    return this.queue.length > 0 || Date.now() < (this.silentUntil || 0) * 1000
  }
}

export const player = new AudioPlayer()

/* -------------------------------------------------------------------------- */
/* Browser speech (fallback only — never used when Gnani keys are configured)  */
/* -------------------------------------------------------------------------- */

let voicesCache = []

export function primeVoices() {
  if (!window.speechSynthesis) return
  voicesCache = window.speechSynthesis.getVoices()
  window.speechSynthesis.onvoiceschanged = () => {
    voicesCache = window.speechSynthesis.getVoices()
  }
}

function pickVoice(lang) {
  const exact = voicesCache.find((v) => v.lang?.toLowerCase() === lang.toLowerCase())
  if (exact) return exact
  const prefix = lang.split('-')[0]
  return voicesCache.find((v) => v.lang?.toLowerCase().startsWith(prefix)) || null
}

export function speakText(text, lang = 'en-IN') {
  if (!text || !window.speechSynthesis) return false
  const utterance = new SpeechSynthesisUtterance(text)
  const voice = pickVoice(lang)
  if (voice) utterance.voice = voice
  utterance.lang = voice?.lang || lang
  utterance.rate = 0.98
  utterance.pitch = 1.0
  window.speechSynthesis.speak(utterance)
  return true
}

export function speechRecognitionAvailable() {
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
}

export function startBrowserRecognition({ lang, onPartial, onFinal, onError }) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Recognition) return null
  const rec = new Recognition()
  rec.lang = lang
  rec.interimResults = true
  rec.continuous = true
  rec.maxAlternatives = 1
  let stopped = false

  rec.onresult = (event) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i]
      const text = result[0]?.transcript?.trim()
      if (!text) continue
      if (result.isFinal) onFinal?.(text)
      else interim += ` ${text}`
    }
    if (interim.trim()) onPartial?.(interim.trim())
  }
  rec.onerror = (e) => {
    if (e.error === 'no-speech' || e.error === 'aborted') return
    onError?.(e.error)
  }
  rec.onend = () => {
    if (!stopped) {
      try {
        rec.start()
      } catch {
        /* browser throttles restarts; ignore */
      }
    }
  }
  try {
    rec.start()
  } catch {
    return null
  }
  return {
    stop() {
      stopped = true
      try {
        rec.stop()
      } catch {
        /* ignore */
      }
    },
  }
}
