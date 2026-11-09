/**
 * Record the narrated NegoAI walkthrough.
 *
 *   node scripts/record_walkthrough.mjs
 *
 * Requires playwright-core in web/node_modules, Chrome, a local server on
 * :8012, the narration WAVs in the temp dir, and a clean Kannada mic clip at
 * scripts/qa_clean_kn.wav. Writes walkthrough.webm + timeline.json to the temp
 * video dir; scripts/make_walkthrough_video.py muxes the narration.
 */
import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

const require = createRequire(new URL('../web/package.json', import.meta.url))
const { chromium } = require('playwright-core')

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8012'
const CHROME =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const WAV = process.env.WAV || 'D:/gnani/scripts/qa_clean_kn.wav'
const TEMP = path.join(os.tmpdir(), 'negoai_video')
const NARRATION = path.join(os.tmpdir(), 'negoai_narration')

await mkdir(TEMP, { recursive: true })
const durations = JSON.parse(
  await (await import('node:fs/promises')).readFile(path.join(NARRATION, 'durations.json'), 'utf8'),
)

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
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: TEMP, size: { width: 1280, height: 720 } },
  permissions: ['microphone'],
})
const page = await context.newPage()
const started = Date.now()
const elapsed = () => (Date.now() - started) / 1000
const marks = {}
const errors = []
page.on('pageerror', (err) => errors.push(err.message))

const pause = (ms) => page.waitForTimeout(ms)
const holdUntil = async (seconds) => {
  const remaining = seconds * 1000 - (Date.now() - started)
  if (remaining > 0) await pause(remaining)
}

// 1. Landing: motto.
marks.landing = 0
await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)
await page.evaluate(() => {
  document.querySelector('#how')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
})
await pause(7000)
await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
await holdUntil(durations.s1 + 1.5)

// 2. Voice console with the clean Kannada request.
marks.console = elapsed()
await page.goto(`${BASE}/console`, { waitUntil: 'domcontentloaded', timeout: 60000 })
await page.waitForSelector('.panel__title', { timeout: 20000 })
await page.waitForFunction(
  () => [...document.querySelectorAll('.panel__meta .pill')].some((el) => /Live/.test(el.textContent)),
  null,
  { timeout: 30000 },
)
await pause(1200)
await page.locator('.mic-btn').click()
try {
  await page.waitForSelector('.confirm__question', { timeout: 22000 })
  await page.getByRole('button', { name: /Yes, confirm/i }).click()
} catch {
  console.log('console: no confirm appeared, continuing')
}
await holdUntil(elapsed() + durations.s2 + 2)

// 3. Negotiation room; DemoBar moves us to /admin when the summary lands.
marks.room = elapsed()
await page.goto(`${BASE}/room?demo=1`, { waitUntil: 'domcontentloaded', timeout: 60000 })
await page.waitForSelector('.panel__title', { timeout: 20000 })
const start = page.getByRole('button', { name: 'Start demo' })
if (await start.count()) await start.click()
await page.waitForURL(/\/admin/, { timeout: 420000 })
marks.admin = elapsed()
await page.waitForSelector('.admin-card__value--big', { timeout: 30000 })
await pause(2500)
await page.getByRole('button', { name: /Approve offer/i }).click()
await page.waitForSelector('.approval-banner', { timeout: 15000 })
await holdUntil(elapsed() + durations.s4 + 5)

// 4. Replay and receipt.
marks.replay = elapsed()
await page.goto(`${BASE}/replay`, { waitUntil: 'domcontentloaded', timeout: 60000 })
await page.waitForSelector('.replay__row', { timeout: 30000 })
await page.locator('.replay__row').first().click()
await page.waitForSelector('.replay__controls', { timeout: 20000 })
await page.getByRole('button', { name: /Skip to end/i }).click()
await page.waitForFunction(
  () => [...document.querySelectorAll('.replay__controls .pill')].some((el) => /Tamper-evident/.test(el.textContent)),
  null,
  { timeout: 20000 },
)
await holdUntil(elapsed() + durations.s5 + 5)

// 5. Close on the receipt, keeping the proof on screen.
marks.close = elapsed()
await holdUntil(elapsed() + durations.s6 + 16)

const video = page.video()
await context.close()
const source = await video.path()
const target = path.join(TEMP, 'walkthrough.webm')
await video.saveAs(target)
await writeFile(
  path.join(NARRATION, 'timeline.json'),
  JSON.stringify({ source: target, marks, errors }, null, 2),
)
console.log(JSON.stringify({ target, marks, errors }, null, 2))
await browser.close()
