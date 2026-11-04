/**
 * Capture the README screenshots from the running app.
 *
 *   cd web && npm install --no-save playwright-core
 *   uvicorn api.main:app --port 8000          # in another terminal
 *   node scripts/capture_screenshots.mjs
 *
 * Uses the locally installed Chrome (no browser download). Writes to
 * docs/screenshots/. Pass BASE_URL to point at a deployed instance.
 */
import { createRequire } from 'node:module'
import { mkdir, rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

// playwright-core is installed under web/ (not a runtime dependency).
const require = createRequire(import.meta.url)
const { chromium } = require(
  fileURLToPath(new URL('../web/node_modules/playwright-core', import.meta.url)),
)

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const OUT = 'docs/screenshots'
const CHROME =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function settle(page) {
  await page.evaluate(() => document.fonts?.ready).catch(() => {})
  await sleep(900)
}

async function shot(page, name) {
  await page.screenshot({
    path: `${OUT}/${name}.jpg`,
    type: 'jpeg',
    quality: 90,
  })
  console.log(`captured ${OUT}/${name}.jpg`)
}

async function open(browser, path, { viewport, deviceScaleFactor = 2, mobile = false }) {
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor,
    isMobile: mobile,
    hasTouch: mobile,
  })
  const page = await context.newPage()
  page.on('pageerror', (err) => console.log('pageerror:', err.message))
  await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' })
  await settle(page)
  return { context, page }
}

async function main() {
  await mkdir(OUT, { recursive: true })
  for (const stale of ['hero-desktop.png', 'hero-mobile.png', 'how-it-works.png']) {
    await rm(`${OUT}/${stale}`, { force: true })
  }

  const browser = await chromium.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--hide-scrollbars'],
  })

  // 1. Landing hero
  const home = await open(browser, '/', {
    viewport: { width: 1440, height: 900 },
  })
  console.log(
    'Poppins loaded:',
    await home.page.evaluate(() => document.fonts.check('600 16px Poppins')),
  )
  await shot(home.page, 'hero-desktop')

  // 2. "How it works" section
  const how = home.page.locator('#how')
  if (await how.count()) {
    await how.scrollIntoViewIfNeeded()
    await sleep(900)
    await how.screenshot({ path: `${OUT}/how-it-works.jpg`, type: 'jpeg', quality: 90 })
    console.log(`captured ${OUT}/how-it-works.jpg`)
  }
  await home.context.close()

  // 3. Mobile landing
  const mobile = await open(browser, '/', {
    viewport: { width: 390, height: 844 },
    mobile: true,
  })
  await shot(mobile.page, 'hero-mobile')
  await mobile.context.close()

  // 4. Voice console (a live session opens on mount)
  const consoleView = await open(browser, '/console', {
    viewport: { width: 1440, height: 900 },
  })
  await consoleView.page.waitForSelector('.panel__title', { timeout: 20000 })
  await sleep(3500)
  await shot(consoleView.page, 'voice-console')
  await consoleView.context.close()

  // 5. Guided demo: negotiation room mid-run, then the admin screen.
  const room = await open(browser, '/room?demo=1', {
    viewport: { width: 1440, height: 900 },
  })
  const start = room.page.getByRole('button', { name: /Start demo/i })
  if (await start.count()) {
    await start.click()
    console.log('guided demo started')
  }
  await room.page.waitForFunction(
    () => document.querySelectorAll('.vendor-card').length >= 3,
    null,
    { timeout: 150000 },
  )
  await sleep(1200)
  await shot(room.page, 'negotiation-room')

  await room.page.waitForURL(/\/admin/, { timeout: 150000 })
  await room.page.waitForSelector('.admin-card__value--big', { timeout: 30000 })
  await sleep(1200)
  await shot(room.page, 'admin-approval')
  await room.context.close()

  // 6. Replay of the stored run
  const replay = await open(browser, '/replay', {
    viewport: { width: 1440, height: 900 },
  })
  await replay.page.waitForSelector('.replay__row', { timeout: 30000 })
  await replay.page.locator('.replay__row').first().click()
  await replay.page.waitForSelector('.replay__controls', { timeout: 30000 })
  await replay.page.getByRole('button', { name: /Skip to end/i }).click()
  await sleep(800)
  await shot(replay.page, 'replay')
  await replay.context.close()

  await browser.close()
  console.log('done')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
