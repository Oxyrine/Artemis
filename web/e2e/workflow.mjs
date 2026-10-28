// Full product walkthrough, the way a judge would use it, with exact expectations from the build spec's answer key.
//   make workflow      (against a freshly seeded server: BASE_URL, default http://localhost:8000)
// It collects every failure instead of stopping at the first, and treats any console or network error as a failure
// unless a step declares it expected. Exit code 1 if anything failed.
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL ?? 'http://localhost:8000'
const HERO = 'CASE-0007', PROBABLE = 'CASE-0008', CONFLICT = 'CASE-0009'
const failures = []
let current = ''
let expected = []        // substrings of errors the current step expects (e.g. a deliberate 404)
const seen = []

const step = async (name, fn) => {
  current = name; expected = []; seen.length = 0
  try { await fn() } catch (e) { failures.push(`${name}: ${String(e.message).split('\n')[0]}`); console.log(`FAIL  ${name}\n      ${String(e.message).split('\n')[0]}`); return }
  const bad = seen.filter((s) => !expected.some((x) => s.includes(x)))
  if (bad.length) { failures.push(`${name}: console/network: ${bad.join(' | ')}`); console.log(`FAIL  ${name}\n      console/network: ${bad.join(' | ')}`) }
  else console.log(`PASS  ${name}`)
}
const check = (cond, msg) => { if (!cond) throw new Error(msg) }
const api = async (path) => (await fetch(`${BASE}/api${path}`)).json()

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await ctx.newPage()
page.setDefaultTimeout(45_000)
page.on('response', (r) => { if (r.status() >= 400) seen.push(`${r.status()} ${new URL(r.url()).pathname}`) })
page.on('pageerror', (e) => seen.push(`pageerror ${e.message.slice(0, 100)}`))
page.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) seen.push(`console ${m.text().slice(0, 100)}`) })

const tile = (label) => page.getByRole('button', { name: new RegExp(`^${label}: \\d+ cases`) })
const tileCount = async (label) => Number((await tile(label).getAttribute('aria-label')).match(/(\d+) cases/)[1])
const runBatchFromUi = async () => {
  await page.getByRole('button', { name: 'Run batch' }).click()
  await page.getByText(/Finished: \d+ of \d+ investigated/).waitFor({ timeout: 180_000 })
}

// ------------------------------------------------------------------------------------------------ first impressions
await step('landing page explains the problem to a newcomer', async () => {
  await page.goto(BASE)
  await page.getByRole('heading', { name: /Someone has to find out why/ }).waitFor()
  for (const t of ['₹15,34,000', '₹15,08,000']) check(await page.getByText(t).first().isVisible(), `worked example shows ${t}`)
  check((await page.getByText('₹26,000').count()) > 0, 'worked example shows the ₹26,000 gap')
  check(await page.getByText(/never calculates money, tax or eligibility/).isVisible(), 'guarantee: the model never does the maths')
  check(await page.getByText(/Nothing is applied without a named reviewer/).isVisible(), 'guarantee: named reviewer')
  check((await page.title()).includes('Artemis'), 'page title mentions Artemis')
})

await step('before any batch: 10 auto-closed, the rest waiting, metrics hint shown', async () => {
  check((await tileCount('Auto-closed')) === 10, 'exactly 10 auto-closed by the matcher')
  for (const s of ['Verified', 'Probable', 'Insufficient', 'Conflicting']) check((await tileCount(s)) === 0, `${s} is 0 before the batch`)
  await page.getByText(/Run a batch to see precision/).waitFor()
})

await step('glossary tooltips define the jargon on focus', async () => {
  await page.locator('.worked-example .term', { hasText: 'TDS' }).first().focus()
  await page.getByText(/Tax Deducted at Source/).waitFor()
})

await step('explainer can be dismissed and brought back', async () => {
  await page.getByRole('button', { name: 'Hide this introduction' }).click()
  check((await page.locator('#welcome').count()) === 0, 'explainer gone')
  await page.reload(); await page.waitForSelector('.welcome-reopen')
  check((await page.locator('#welcome').count()) === 0, 'stays dismissed after a reload')
  await page.getByRole('button', { name: /What is this, and how does it work/ }).click()
  await page.locator('#welcome').waitFor()
})

// ------------------------------------------------------------------------------------------------ the guided demo
await step('guided demo: Show me scrolls to the explainer', async () => {
  await page.getByRole('button', { name: 'Guided demo' }).first().click()
  await page.getByText(/Guided demo · step 1 of 7/).waitFor()
  await page.getByRole('button', { name: /Show me/ }).click()
  await page.locator('#welcome').waitFor()
})

await step('guided demo: Run it for me investigates every exception (within the time budget)', async () => {
  await page.getByRole('button', { name: /Next/ }).click()
  const started = Date.now()
  await page.getByRole('button', { name: /Run it for me/ }).click()
  await page.getByText(/Done: \d+ of \d+ investigated/).waitFor({ timeout: 180_000 })
  const seconds = (Date.now() - started) / 1000
  console.log(`      batch took ${seconds.toFixed(1)} s`)
  check(seconds < Number(process.env.BATCH_BUDGET_S ?? 20), `the batch took ${seconds.toFixed(1)} s (budget ${process.env.BATCH_BUDGET_S ?? 20} s)`)
})

await step('batch result matches the answer key: 10 / 16 / 6 / 4 / 4', async () => {
  const got = { auto: await tileCount('Auto-closed'), ver: await tileCount('Verified'), prob: await tileCount('Probable'), ins: await tileCount('Insufficient'), con: await tileCount('Conflicting') }
  check(JSON.stringify(got) === JSON.stringify({ auto: 10, ver: 16, prob: 6, ins: 4, con: 4 }), `got ${JSON.stringify(got)}`)
})

await step('metrics: zero false clears, verified precision 100%', async () => {
  await page.getByText('Verified precision').waitFor()
  const text = await page.locator('#metrics').innerText()
  check(/100%/.test(text), 'verified precision shows 100%')
  const m = await api('/metrics')
  check(m.verified_precision === 1 && m.false_clears.length === 0 && m.red_team_applied.length === 0, `precision ${m.verified_precision}, false clears ${m.false_clears}`)
})

await step('the batch cannot be run twice: button disabled with the reason', async () => {
  await page.getByRole('button', { name: /Close the guided demo/ }).click()
  check(await page.locator('#run-batch').isDisabled(), 'Run batch is disabled when nothing is new')
  await page.getByText(/already been investigated/).waitFor()
})

// ------------------------------------------------------------------------------------------------ the queue
await step('receipt queue: search, filter and clear', async () => {
  await page.getByLabel('Search receipts').fill('UTR839201')
  await page.getByRole('link', { name: HERO, exact: true }).waitFor()
  check((await page.getByRole('link', { name: /^CASE-\d{4}$/ }).count()) === 1, 'search narrows to the hero case')
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await page.getByLabel('Filter by status').selectOption('CONFLICTING')
  await page.waitForFunction(() => document.querySelectorAll('.desktop-case-list tbody tr').length === 4)
  await page.getByRole('button', { name: 'Clear filters' }).click()
})

await step('outcome tile filters the queue', async () => {
  await tile('Probable').click()
  await page.waitForFunction(() => document.querySelectorAll('.desktop-case-list tbody tr').length === 6)
  await tile('Probable').click()
})

// ------------------------------------------------------------------------------------------------ the hero case
await step('hero case: grade explanation, variance closes to zero, evidence graph, trace', async () => {
  await page.getByLabel('Search receipts').fill(HERO)
  await page.getByRole('link', { name: HERO, exact: true }).click()
  await page.getByText('Why Verified?').waitFor()
  check((await page.getByTestId('unexplained').innerText()).replace(/\D/g, '') === '0', 'unexplained is ₹0')
  await page.locator('.react-flow__node').first().waitFor({ timeout: 30_000 })
  check((await page.locator('.react-flow__node').count()) >= 6, 'graph shows receipt, invoices, adjustment, evidence and rule')
  check((await page.getByText('Agent trace').count()) > 0, 'agent trace present')
  check((await page.getByText('Check the tax-credit extract').count()) > 0, 'trace uses plain-language tool names')
})

await step('hero case: approve as the analyst and the audit event appears without a reload', async () => {
  const acting = page.getByLabel('Acting as')
  await acting.selectOption(await acting.locator('option', { hasText: '(analyst' }).first().getAttribute('value'))
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  await page.getByRole('status').filter({ hasText: /recorded by .*audit event #\d+/ }).waitFor()
  await page.getByText(/This case is Applied/).waitFor()
  check((await api(`/cases/${HERO}`)).state === 'APPLIED', 'the case is APPLIED on the server')
})

// ------------------------------------------------------------------------------------------------ the twins
await step('Probable twin: approval is blocked and the reason is shown', async () => {
  await page.goto(`${BASE}/cases/${PROBABLE}`)
  await page.getByText('Why only Probable?').waitFor()
  check(await page.getByRole('button', { name: 'Approve', exact: true }).isDisabled(), 'Approve disabled')
  await page.getByText(/Probable: waiting for the missing evidence/).first().waitFor()
})

await step('Conflicting twin: shows the disagreeing pair', async () => {
  await page.goto(`${BASE}/cases/${CONFLICT}`)
  await page.getByText('Why Conflicting?').waitFor()
  await page.getByTestId('flag-amount').first().waitFor()
  check(await page.getByRole('button', { name: 'Approve', exact: true }).isDisabled(), 'Approve disabled')
})

await step('Insufficient duplicate-payment case: refused, flagged, refund recommendation', async () => {
  const dup = (await api('/cases')).cases.find((c) => c.duplicate)
  check(dup, 'a duplicate case exists')
  await page.goto(`${BASE}/cases/${dup.case_id}`)
  await page.getByText('Duplicate payment').first().waitFor()
  await page.getByText('Why Insufficient?').waitFor()
  check(await page.getByRole('button', { name: 'Approve', exact: true }).isDisabled(), 'Approve disabled')
})

// ------------------------------------------------------------------------------------------------ reviewer actions
await step('request evidence needs a comment, then moves the case to awaiting evidence', async () => {
  const verified = (await api('/cases?status=VERIFIED')).cases.find((c) => c.state === 'PENDING_APPROVAL' && c.case_id !== HERO)
  await page.goto(`${BASE}/cases/${verified.case_id}`)
  await page.getByRole('button', { name: 'Request evidence' }).waitFor()
  check(await page.getByRole('button', { name: 'Request evidence' }).isDisabled(), 'disabled without a comment')
  await page.getByLabel(/Comment/).fill('Please send the TDS certificate')
  await page.getByRole('button', { name: 'Request evidence' }).click()
  await page.getByRole('status').filter({ hasText: /Request evidence recorded by .*Awaiting evidence/ }).waitFor()
  // the panel stays up in this state (spec): every action is disabled and the policy says why
  for (const n of ['Approve', 'Request evidence', 'Reject']) check(await page.getByRole('button', { name: n, exact: true }).isDisabled(), `${n} is disabled while evidence is awaited`)
  await page.getByText(/waiting for the missing evidence/).first().waitFor()
  check((await api(`/cases/${verified.case_id}`)).state === 'AWAITING_EVIDENCE', 'the case is AWAITING_EVIDENCE on the server')
})

await step('reject asks for confirmation and records the decision', async () => {
  const verified = (await api('/cases?status=VERIFIED')).cases.find((c) => c.state === 'PENDING_APPROVAL')
  await page.goto(`${BASE}/cases/${verified.case_id}`)
  await page.getByLabel(/Comment/).fill('Customer disputes the invoice')
  await page.getByRole('button', { name: 'Reject', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Reject case' }).click()
  await page.getByText(/This case is Rejected/).waitFor()
})

// ------------------------------------------------------------------------------------------------ compare and audit
await step('agent paths: three cases, three different tool sequences', async () => {
  await page.getByRole('link', { name: 'Agent paths' }).click()
  await page.getByRole('status').filter({ hasText: '3 cases, 3 different tool sequences' }).waitFor()
  check((await page.getByRole('article').count()) === 3, 'three columns')
  const t = await page.locator('.compare-grid').innerText()
  check(/Nothing filed/.test(t) && /₹20,000/.test(t) && /No: 1 contradiction/.test(t), 'twins show their different evidence')
})

await step('audit ledger: chain verifies, checkpoint downloads', async () => {
  await page.getByRole('link', { name: 'Audit ledger' }).click()
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await page.getByTestId('verify-ok').waitFor()
  const dl = await page.request.get(`${BASE}/api/audit/checkpoint`)
  check(dl.ok(), 'signed checkpoint downloads')
  await page.getByLabel('Filter by case id').fill(HERO)
  await page.waitForFunction((c) => [...document.querySelectorAll('tbody tr')].every((r) => r.innerText.includes(c)), HERO)
  await page.getByLabel('Filter by case id').fill('')
})

await step('audit ledger: tampering breaks the chain at a visible event; reset heals it', async () => {
  await page.getByRole('button', { name: 'Simulate tampering' }).click()
  await page.getByTestId('verify-broken').waitFor()
  const row = page.locator('.row-broken')
  await row.waitFor()
  check(await row.isVisible(), 'the broken event is highlighted')
  await page.getByRole('button', { name: 'Reset environment' }).click()
  await page.getByTestId('verify-ok').waitFor()
})

// ------------------------------------------------------------------------------------------------ resilience
await step('after the reset everything starts clean and the batch can run again', async () => {
  await page.getByRole('link', { name: 'Reconciliation' }).click()
  await page.getByText(/Run a batch to see precision/).waitFor()
  check((await tileCount('Auto-closed')) === 10 && (await tileCount('Verified')) === 0, 'fresh state')
  await runBatchFromUi()
  check((await tileCount('Verified')) === 16, 'second run reproduces the answer key')
})

await step('guided demo finishes: later steps navigate', async () => {
  await page.getByRole('button', { name: 'Guided demo' }).first().click()
  for (let i = 0; i < 6; i++) await page.getByRole('button', { name: /Next/ }).click()
  await page.getByRole('button', { name: 'Finish' }).click()
  check((await page.getByRole('complementary', { name: 'Guided demo' }).count()) === 0, 'guide closed')
})

await step('guided demo: metrics can be revisited without changing routes', async () => {
  await page.getByRole('button', { name: 'Guided demo', exact: true }).click()
  for (let i = 0; i < 6; i++) await page.getByRole('button', { name: 'Next', exact: true }).click()
  await page.getByRole('button', { name: 'See the metrics' }).click()
  await page.waitForFunction(() => document.getElementById('metrics').getBoundingClientRect().top < innerHeight - 100)
  await page.keyboard.press('Control+Home')
  await page.waitForFunction(() => scrollY < 3)
  await page.getByRole('button', { name: 'See the metrics' }).click()
  await page.waitForFunction(() => document.getElementById('metrics').getBoundingClientRect().top < innerHeight - 100)
})

await step('guided demo: minimize and resume preserve the current step', async () => {
  await page.getByRole('button', { name: 'Minimize the guided demo' }).click()
  check(!(await page.getByRole('heading', { name: 'The scoreboard' }).count()), 'expanded guide content is hidden')
  await page.getByRole('button', { name: 'Expand the guided demo' }).click()
  await page.getByRole('heading', { name: 'The scoreboard' }).waitFor()
  await page.getByRole('button', { name: 'Finish', exact: true }).click()
})

await step('unknown routes and cases fail politely', async () => {
  expected = ['404']
  await page.goto(`${BASE}/cases/CASE-9999`)
  await page.getByText(/There is no case CASE-9999/).waitFor()
  await page.goto(`${BASE}/not-a-page`)
  await page.getByText(/not found|doesn.t exist|404/i).first().waitFor()
})

await step('dark theme toggles without breaking the page', async () => {
  await page.goto(BASE)
  await page.getByRole('button', { name: /Switch to dark theme/ }).click()
  check(await page.evaluate(() => document.documentElement.classList.contains('dark')), 'dark class set')
  await page.getByRole('button', { name: /Switch to light theme/ }).click()
})

// ------------------------------------------------------------------------------------------------ a phone
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })
const mp = await phone.newPage()
mp.setDefaultTimeout(45_000)
mp.on('response', (r) => { if (r.status() >= 400) seen.push(`${r.status()} ${new URL(r.url()).pathname}`) })
mp.on('pageerror', (e) => seen.push(`pageerror ${e.message.slice(0, 100)}`))
const noSideScroll = async (label) => check(await mp.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${label} scrolls sideways on a phone`)

await step('phone: every page fits the screen', async () => {
  for (const [label, path] of [['dashboard', '/'], ['case', `/cases/${HERO}`], ['agent paths', '/compare'], ['audit', '/audit']]) {
    await mp.goto(BASE + path); await mp.waitForTimeout(1200); await noSideScroll(label)
  }
})

await step('phone: the menu opens, scrolls to the reviewer and closes on navigation', async () => {
  await mp.goto(BASE)
  await mp.getByRole('button', { name: 'Open navigation' }).click()
  const sb = mp.locator('.workspace-sidebar')
  await sb.waitFor()
  const reachable = await mp.evaluate(() => { const r = document.querySelector('.reviewer-identity'); r.scrollIntoView({ block: 'end' }); const b = r.getBoundingClientRect(); return b.top >= 0 && b.bottom <= innerHeight })
  check(reachable, 'reviewer row reachable in the menu')
  await mp.getByRole('link', { name: 'Agent paths' }).click()
  await mp.waitForFunction(() => !document.querySelector('.workspace-sidebar.menu-open'))
})

await step('phone: the guided demo panel fits and works', async () => {
  await mp.goto(BASE)
  await mp.getByRole('button', { name: 'Open navigation' }).click()
  await mp.getByRole('button', { name: 'Guided demo' }).first().click()
  const box = await mp.getByRole('complementary', { name: 'Guided demo' }).boundingBox()
  check(box.x >= 0 && box.x + box.width <= 390, 'guide panel inside the screen')
  await mp.getByRole('button', { name: /Next/ }).click()
  await mp.getByText(/step 2 of 7/).waitFor()
})

await browser.close()
console.log(failures.length ? `\n${failures.length} FAILED:\n- ${failures.join('\n- ')}` : '\nworkflow passed: every step behaved')
process.exit(failures.length ? 1 : 0)
