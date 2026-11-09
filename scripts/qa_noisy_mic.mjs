/**
 * Temporary QA harness: feed a noisy WAV through Chrome's fake microphone and
 * observe the real console pipeline (getUserMedia -> worklet -> WebSocket).
 *
 *   WAV=C:/path/noisy.wav node scripts/qa_noisy_mic.mjs
 *
 * Requires playwright-core in web/node_modules and a local uvicorn on :8000.
 */
import { createRequire } from 'node:module'

const require = createRequire(new URL('../web/package.json', import.meta.url))
const { chromium } = require('playwright-core')

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const WAV = process.env.WAV
const CHROME =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const LISTEN_MS = Number(process.env.LISTEN_MS || 30000)

if (!WAV) {
  console.error('WAV is required')
  process.exit(2)
}

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: [
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    `--use-file-for-fake-audio-capture=${WAV}`,
    '--autoplay-policy=no-user-gesture-required',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
  ],
})

const context = await browser.newContext({
  viewport: { width: 1280, height: 900 },
  permissions: ['microphone'],
})
const page = await context.newPage()

const events = []
const sent = { audio: 0, pcmBytes: 0 }
const consoleErrors = []

page.on('console', (msg) => {
  if (msg.type() === 'error' || msg.type() === 'warning') {
    consoleErrors.push(`${msg.type()}: ${msg.text()}`)
  }
})
page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`))

page.on('websocket', (ws) => {
  console.log('socket:', ws.url())
  ws.on('framereceived', (frame) => {
    if (typeof frame.payload !== 'string') return
    try {
      events.push(JSON.parse(frame.payload))
    } catch {
      /* non-JSON frame */
    }
  })
  ws.on('framesent', (frame) => {
    if (typeof frame.payload !== 'string') return
    try {
      const msg = JSON.parse(frame.payload)
      if (msg.type === 'audio') {
        sent.audio += 1
        sent.pcmBytes += Math.floor((msg.pcm.length * 3) / 4)
      }
    } catch {
      /* binary or non-JSON */
    }
  })
})

await page.goto(`${BASE}/console`, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.panel__title', { timeout: 20000 })

await page.waitForFunction(
  () => [...document.querySelectorAll('.panel__meta .pill')].some((el) => /Live/.test(el.textContent)),
  null,
  { timeout: 30000 },
)
console.log('gateway ready')
await page.waitForTimeout(1200)

const mic = page.locator('.mic-btn')
await mic.click()
await page.waitForTimeout(1500)
console.log('mic pressed:', await mic.getAttribute('aria-pressed'))

await page.waitForTimeout(LISTEN_MS)

// If the pipeline recognised the request, confirm it so the agent can proceed.
let confirmed = false
if (await page.locator('.confirm__question').count()) {
  await page.getByRole('button', { name: /Yes, confirm/i }).click()
  confirmed = true
  await page.waitForTimeout(12000)
}

const snapshot = await page.evaluate(() => ({
  status: document.querySelector('.panel__meta .pill')?.textContent?.trim(),
  mic: document.querySelector('.mic-btn')?.getAttribute('aria-pressed'),
  orb: document.querySelector('.orb')?.className || null,
  lines: [...document.querySelectorAll('.line')].map((line) => ({
    meta: line.querySelector('.line__meta')?.innerText?.replace(/\s+/g, ' ').trim(),
    text: line.querySelector('.line__text')?.innerText,
    gloss: line.querySelector('.line__gloss')?.innerText,
  })),
  partial: document.querySelector('.line--partial .line__text')?.innerText || null,
  confirm: document.querySelector('.confirm__question')?.innerText || null,
  notices: [...document.querySelectorAll('.notice')].map((n) => n.innerText),
  requests: [...document.querySelectorAll('.requests__row')].map((r) => r.innerText),
  errorText: document.querySelector('.error')?.innerText || null,
}))

const relevant = events.filter((e) =>
  ['ready', 'transcript', 'partial', 'confirm', 'demand', 'confirm_clear', 'notice', 'error', 'admin', 'demand_saved', 'phase'].includes(e.type),
)
const levels = events.filter((e) => e.type === 'level').map((e) => e.value)

console.log(
  JSON.stringify(
    {
      micFramesSent: sent.audio,
      pcmBytesSent: sent.pcmBytes,
      levelEvents: levels.length,
      maxLevel: levels.length ? Math.max(...levels) : 0,
      transcriptEvents: relevant.filter((e) => e.type === 'transcript').map((e) => ({ role: e.role, text: e.text })),
      partials: relevant.filter((e) => e.type === 'partial' && e.text).map((e) => e.text),
      confirms: relevant.filter((e) => e.type === 'confirm').map((e) => e.text),
      demands: relevant.filter((e) => e.type === 'demand').map((e) => e.slots),
      notices: relevant.filter((e) => e.type === 'notice').map((e) => e.text),
      errors: relevant.filter((e) => e.type === 'error').map((e) => e.message),
      confirmed,
      snapshot,
      consoleErrors,
    },
    null,
    2,
  ),
)

await browser.close()
