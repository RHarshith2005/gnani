import test from 'node:test'
import assert from 'node:assert/strict'

globalThis.window = {
  location: { protocol: 'https:', host: 'negoai.test' },
  speechSynthesis: { cancel() {}, getVoices: () => [], speak() {} },
}
globalThis.SpeechSynthesisUtterance = class {}

class MockWebSocket {
  static OPEN = 1
  static CONNECTING = 0
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.CONNECTING
    this.sent = []
    MockWebSocket.instances.push(this)
  }

  send(message) {
    this.sent.push(JSON.parse(message))
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen()
  }

  close() {
    this.readyState = 3
  }
}

globalThis.WebSocket = MockWebSocket

const [{ voiceClient }, { player }, { useSession }, { installEventSideEffects }] = await Promise.all([
  import('./client.js'),
  import('./audio.js'),
  import('../state/session.js'),
  import('./voice.js'),
])
installEventSideEffects()

test('unexpected disconnect stops audio without auto-starting another session', async () => {
  useSession.getState().reset()
  MockWebSocket.instances.length = 0
  voiceClient.ws = null
  voiceClient.sessionStarted = false
  voiceClient.pendingHello = false
  voiceClient.pending.length = 0
  voiceClient.start('live', 'en-IN')

  const firstSocket = MockWebSocket.instances[0]
  firstSocket.open()
  assert.equal(firstSocket.sent.filter((message) => message.type === 'hello').length, 1)

  let stoppedSources = 0
  let audioPushes = 0
  player.ctx = { currentTime: 12 }
  player.queue = [{ stop() { stoppedSources += 1 } }]
  const originalPush = player.push
  player.push = () => { audioPushes += 1 }
  firstSocket.onclose()
  voiceClient.connect()
  firstSocket.onmessage({
    data: JSON.stringify({
      type: 'audio',
      pcm: btoa('\x00\x00'),
      sampleRate: 16000,
      utterance_id: 1,
      epoch: 0,
    }),
  })

  await new Promise((resolve) => setTimeout(resolve, 30))
  assert.equal(MockWebSocket.instances.length, 1)
  assert.equal(firstSocket.sent.filter((message) => message.type === 'hello').length, 1)
  assert.equal(player.queue.length, 0)
  assert.equal(stoppedSources, 1)
  assert.equal(audioPushes, 0)
  assert.ok(useSession.getState().notices.some((notice) => notice.text.includes('Tap to continue')))

  voiceClient.close()
  player.push = originalPush
  player.ctx = null
  player.silentUntil = 0
})
