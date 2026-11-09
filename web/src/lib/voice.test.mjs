import test from 'node:test'
import assert from 'node:assert/strict'

const spoken = []

globalThis.window = {
  location: { protocol: 'http:', host: 'localhost' },
  speechSynthesis: {
    speak(utterance) {
      spoken.push(utterance)
    },
  },
}
globalThis.SpeechSynthesisUtterance = class {
  constructor(text) {
    this.text = text
  }
}

const { installEventSideEffects } = await import('./voice.js')
const { useSession } = await import('../state/session.js')

installEventSideEffects()

function reset(tts) {
  useSession.getState().reset()
  useSession.setState({ capabilities: { stt: 'browser', tts }, orb: 'idle' })
  spoken.length = 0
}

test('Gnani TTS agent events do not invoke browser speech synthesis', () => {
  reset('gnani')

  useSession.getState().applyEvent({
    type: 'agent',
    text: 'Spoken Kannada text',
    subtitle: 'English subtitle',
    lang: 'kn-IN',
    tts: 'gnani',
  })

  assert.equal(spoken.length, 0)
  useSession.getState().setOrb('idle')
})

test('browser TTS speaks agent text once and does not speak the subtitle', () => {
  reset('browser')

  useSession.getState().applyEvent({
    type: 'agent',
    text: 'Spoken Kannada text',
    subtitle: 'English subtitle',
    lang: 'kn-IN',
    tts: 'browser',
  })

  assert.equal(spoken.length, 1)
  assert.equal(spoken[0].text, 'Spoken Kannada text')
  assert.equal(spoken[0].lang, 'kn-IN')
  useSession.getState().setOrb('idle')
})
