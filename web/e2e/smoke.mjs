// UI smoke (spec: "run batch, open hero case, approve, verify chain"). Needs a running server with the built UI:
//   make smoke            (builds web/, then runs this against BASE_URL, default http://localhost:8000)
// The server must be in demo mode (POST /reset enabled) and have no ARTEMIS_API_TOKEN, or the buttons will 401.
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL ?? 'http://localhost:8000'
const HERO = process.env.HERO_CASE ?? 'CASE-0007' // UTR839201
const step = (msg) => console.log(`- ${msg}`)

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined })
const page = await browser.newPage()
page.setDefaultTimeout(60_000)
try {
  await page.goto(BASE)

  step('reset the environment')
  await page.getByRole('button', { name: 'Reset environment' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Reset', exact: true }).click()
  await page.getByRole('dialog').waitFor({ state: 'detached' })

  step('run the batch with the demo agent')
  await page.getByRole('button', { name: 'Run batch' }).click()
  await page.getByText(/Finished: \d+ of \d+ investigated/).waitFor({ timeout: 180_000 })

  step(`open ${HERO} (the hero case)`)
  await page.getByRole('link', { name: HERO, exact: true }).click()
  await page.getByTestId('unexplained').waitFor()
  const unexplained = (await page.getByTestId('unexplained').innerText()).replace(/[^\d]/g, '')
  if (Number(unexplained) !== 0) throw new Error(`hero case does not close to zero: "${unexplained}"`)

  step('approve it as the analyst')
  const acting = page.getByLabel('Acting as')
  await acting.selectOption(await acting.locator('option', { hasText: '(analyst' }).first().getAttribute('value'))
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  await page.getByRole('status').filter({ hasText: /recorded by/ }).waitFor()

  step('verify the audit chain')
  await page.getByRole('link', { name: 'Audit' }).click()
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await page.getByTestId('verify-ok').waitFor()

  step('compare the hero case with its twins')
  await page.getByRole('link', { name: 'Agent paths' }).click()
  await page.getByRole('status').filter({ hasText: /different tool sequences/ }).waitFor()
  if ((await page.getByRole('article').count()) !== 3) throw new Error('expected the hero case and two twins')

  step('tamper with the ledger and watch verification fail, then reset')
  await page.getByRole('link', { name: 'Audit ledger' }).click()
  await page.getByRole('button', { name: 'Simulate tampering' }).click()
  await page.getByTestId('verify-broken').waitFor()
  await page.getByRole('button', { name: 'Reset environment' }).click()
  await page.getByTestId('verify-ok').waitFor()

  step('run the batch from the guided demo (the environment was just reset)')
  await page.getByRole('link', { name: 'Reconciliation' }).click()
  await page.getByRole('button', { name: 'Guided demo' }).first().click()
  await page.getByRole('button', { name: /Next/ }).click()
  await page.getByRole('button', { name: /Run it for me/ }).click()
  await page.getByText(/Done: \d+ of \d+ investigated/).waitFor({ timeout: 180_000 })

  console.log('smoke passed')
} catch (e) {
  await page.screenshot({ path: 'e2e/failure.png', fullPage: true }).catch(() => {})
  console.error('smoke FAILED:', e.message, '\n(screenshot: web/e2e/failure.png)')
  process.exitCode = 1
} finally {
  await browser.close()
}
