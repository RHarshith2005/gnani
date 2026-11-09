import { useSession } from '../state/session.js'
import { voiceClient } from './client.js'
import {
  base64ToInt16,
  createMic,
  player,
  primeVoices,
  speakText,
  speechRecognitionAvailable,
  startBrowserRecognition,
} from './audio.js'

let mic = null
let recognition = null
let recognitionLang = null
let lastAudioAt = 0
let pendingSpeech = null
let speechTimer = 0
let levelTimer = 0

/** The server tells us whether it has real STT/TTS; the UI adapts. */
function usingGnaniSTT() {
  return useSession.getState().capabilities?.stt === 'gnani'
}
function usingGnaniTTS() {
  return useSession.getState().capabilities?.tts === 'gnani'
}

function startSyntheticLevel() {
  stopSyntheticLevel()
  const store = useSession.getState()
  if (store.orb !== 'speaking') return
  const t0 = performance.now()
  levelTimer = setInterval(() => {
    const s = useSession.getState()
    if (s.orb !== 'speaking') return stopSyntheticLevel()
    const t = (performance.now() - t0) / 1000
    const env = 0.35 + 0.28 * Math.abs(Math.sin(t * 6.1)) + 0.18 * Math.abs(Math.sin(t * 11.7 + 1.3))
    s.setLevel(Math.min(1, env))
  }, 60)
}

function stopSyntheticLevel() {
  if (levelTimer) clearInterval(levelTimer)
  levelTimer = 0
}

function scheduleSpeech() {
  // If the gateway sends Timbre audio, browser TTS stays out of the way.
  if (pendingSpeech && Date.now() - lastAudioAt > 900) {
    const { text, lang } = pendingSpeech
    pendingSpeech = null
    if (!usingGnaniTTS() || Date.now() - lastAudioAt > 2500) {
      speakText(text, lang)
    }
  }
}

let sideEffectsInstalled = false

export function installEventSideEffects() {
  if (sideEffectsInstalled) return
  sideEffectsInstalled = true
  let prevOrb = useSession.getState().orb
  useSession.subscribe((state) => {
    if (state.orb !== prevOrb) {
      prevOrb = state.orb
      if (state.orb === 'speaking') {
        if (!usingGnaniTTS()) startSyntheticLevel()
      } else {
        stopSyntheticLevel()
      }
      if (state.orb === 'listening') {
        player.stop()
      }
    }
  })

  const original = useSession.getState().applyEvent
  useSession.setState({
    applyEvent: (event) => {
      if (event?.type === 'audio' && event.pcm) {
        lastAudioAt = Date.now()
        try {
          player.push(base64ToInt16(event.pcm), event.sampleRate || 16000)
        } catch {
          /* malformed chunk, ignore */
        }
      }
      if (event?.type === 'agent') {
        pendingSpeech = {
          text: event.subtitle || event.text,
          lang: event.lang || useSession.getState().language,
        }
        lastAudioAt = 0
        clearTimeout(speechTimer)
        speechTimer = setTimeout(scheduleSpeech, 700)
      }
      if (event?.type === 'transcript' && event.role === 'resident') {
        player.stop()
      }
      original(event)
    },
  })
}

/* -------------------------------------------------------------------------- */

export async function enableMic() {
  const store = useSession.getState()
  await player.unlock()
  primeVoices()
  voiceClient.connect()
  store.addNotice({ text: 'Microphone on — speak in your language.', level: 'info' })
  store.setMicOn(true)

  const lang = store.language

  if (usingGnaniSTT()) {
    try {
      mic = await createMic({
        onChunk: (int16) => voiceClient.audio(int16),
      })
    } catch (err) {
      store.addNotice({
        text: `Mic unavailable (${err.message}). Use the text box.`,
        level: 'warn',
      })
      store.setMicOn(false)
    }
    return
  }

  // No server STT yet: keep capture local and let Chrome do the transcript.
  if (speechRecognitionAvailable()) {
    if (recognition && recognitionLang !== lang) {
      recognition.stop()
      recognition = null
    }
    if (!recognition) {
      recognitionLang = lang
      recognition = startBrowserRecognition({
        lang,
        onPartial: (text) => useSession.getState().setPartial(text),
        onFinal: (text) => {
          useSession.getState().setPartial('')
          useSession.getState().addLine({ role: 'resident', text, lang })
          voiceClient.text(text)
        },
        onError: (err) =>
          useSession.getState().addNotice({
            text: `Speech recognition: ${err}. Type instead.`,
            level: 'warn',
          }),
      })
    }
  } else {
    store.addNotice({
      text: 'This browser has no speech recognition. Type instead — same agent brain.',
      level: 'warn',
    })
  }
}

export function disableMic() {
  mic?.stop()
  mic = null
  recognition?.stop()
  recognition = null
  recognitionLang = null
  useSession.getState().setMicOn(false)
  useSession.getState().setLevel(0)
  useSession.getState().setPartial('')
}

export function toggleMic() {
  const on = useSession.getState().micOn
  if (on) disableMic()
  else enableMic().catch((err) => useSession.getState().setError(err.message))
}

/* ----- negotiation playback controls (Prompt 10) --------------------------- */

export function pauseNegotiation() {
  player.pause()
  voiceClient.control('pause')
}

export function resumeNegotiation() {
  voiceClient.control('resume')
  player.resume()
}

export function stopNegotiation() {
  player.stop()
  voiceClient.control('stop')
}

export function skipVendor() {
  player.stop()
  voiceClient.control('skip')
}

/* -------------------------------------------------------------------------- */

export const voice = {
  startDemo(language = 'kn-IN') {
    player.unlock().catch(() => {})
    primeVoices()
    const store = useSession.getState()
    store.reset()
    useSession.setState({ demoRunning: true, mode: 'guided', language })
    voiceClient.start('guided', language)
  },

  startLive(language) {
    player.unlock().catch(() => {})
    primeVoices()
    const store = useSession.getState()
    const lang = language || store.language
    store.reset()
    useSession.setState({ mode: 'live', language: lang })
    voiceClient.start('live', lang)
  },

  sendText(text) {
    const trimmed = text?.trim()
    if (!trimmed) return
    // The gateway echoes a resident transcript for every message. Adding a
    // local line here as well made typed input appear twice.
    voiceClient.connect()
    voiceClient.text(trimmed)
  },

  setLanguage(language) {
    const store = useSession.getState()
    store.setLanguage(language)
    voiceClient.send({ type: 'language', language })
    if (store.micOn && !usingGnaniSTT()) {
      disableMic()
      enableMic().catch(() => {})
    }
  },

  approve(decision, note = '') {
    voiceClient.approve(decision, note)
    useSession.getState().addLine({
      role: 'system',
      text: decision === 'approved' ? 'Committee approved the offer.' : 'Committee rejected the offer.',
    })
  },

  reset() {
    player.stop()
    stopSyntheticLevel()
    voiceClient.reset()
    useSession.getState().reset()
  },

  bargeIn() {
    player.stop()
    voiceClient.bargeIn()
  },

  pause: pauseNegotiation,
  resume: resumeNegotiation,
  stop: stopNegotiation,
  skip: skipVendor,

  toggleMic,
  enableMic,
  disableMic,
  player,
}
