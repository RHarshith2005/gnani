import { useSession } from '../state/session.js'
import { voiceClient } from './client.js'
import {
  base64ToInt16,
  createMic,
  player,
  primeVoices,
  rms,
  speakText,
  speechRecognitionAvailable,
  startBrowserRecognition,
} from './audio.js'

let mic = null
let recognition = null
let recognitionLang = null
let levelTimer = 0
let recognitionResumeTimer = 0
let highMicLevelMs = 0
let currentEpoch = 0
let activeUtteranceId = null

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

function monitorMicForBargeIn(int16) {
  if (!useSession.getState().micOn || !player.speaking || activeUtteranceId == null) {
    highMicLevelMs = 0
    return false
  }
  highMicLevelMs = rms(int16) >= 0.3 ? highMicLevelMs + int16.length / 16 : 0
  if (highMicLevelMs >= 250) {
    highMicLevelMs = 0
    voice.bargeIn()
  }
  return true
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
  player.onPlaybackDone = (utteranceId, epoch) => {
    if (epoch === currentEpoch) voiceClient.playbackDone(utteranceId, epoch)
  }
  useSession.setState({
    applyEvent: (event) => {
      if (event?.type === 'ready') {
        currentEpoch = Number(event.epoch) || 0
        activeUtteranceId = null
      }
      if (
        (event?.type === 'agent' || event?.type === 'audio') &&
        Number.isInteger(event.epoch) &&
        event.epoch < currentEpoch
      ) {
        return
      }
      if (event?.type === 'interrupt') {
        currentEpoch = Math.max(currentEpoch, Number(event.epoch) || 0)
        activeUtteranceId = null
        highMicLevelMs = 0
        player.stop()
        clearTimeout(recognitionResumeTimer)
        recognitionResumeTimer = setTimeout(() => recognition?.resume(), 400)
      }
      if (event?.type === 'agent') {
        currentEpoch = Math.max(currentEpoch, Number(event.epoch) || 0)
        activeUtteranceId = event.utterance_id
        if (event.tts === 'browser') {
          recognition?.pause()
          clearTimeout(recognitionResumeTimer)
          player.setBrowserSpeaking(true)
          const started = speakText(event.text, event.lang, {
            onend: () => {
              player.setBrowserSpeaking(false)
              if (Number.isInteger(event.utterance_id)) {
                voiceClient.playbackDone(event.utterance_id, event.epoch)
              }
              recognitionResumeTimer = setTimeout(() => recognition?.resume(), 400)
            },
          })
          if (!started) {
            player.setBrowserSpeaking(false)
            voiceClient.playbackDone(event.utterance_id, event.epoch)
          }
        }
      }
      if (
        event?.type === 'audio' &&
        event.pcm &&
        (event.epoch == null || event.epoch >= currentEpoch) &&
        (event.utterance_id == null || event.utterance_id === activeUtteranceId)
      ) {
        currentEpoch = Math.max(currentEpoch, Number(event.epoch) || 0)
        try {
          player.push(base64ToInt16(event.pcm), event.sampleRate || 16000, {
            utteranceId: event.utterance_id,
            epoch: event.epoch,
          })
        } catch {
          /* malformed chunk, ignore */
        }
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
        onChunk: (int16) => {
          if (!useSession.getState().micOn || monitorMicForBargeIn(int16)) return
          voiceClient.audio(int16)
        },
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
    try {
      mic = await createMic({ onChunk: monitorMicForBargeIn })
    } catch {
      // Browser recognition remains available even if the PCM meter is unsupported.
    }
  } else {
    store.addNotice({
      text: 'This browser has no speech recognition. Type instead — same agent brain.',
      level: 'warn',
    })
  }
}

export function disableMic() {
  clearTimeout(recognitionResumeTimer)
  recognitionResumeTimer = 0
  highMicLevelMs = 0
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
    activeUtteranceId = null
    voiceClient.bargeIn()
  },

  resume() {
    voiceClient.resume()
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
