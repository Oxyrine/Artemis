# Artemis production walkthrough — 28 October 2026

Deployment: https://artemis-lime.vercel.app. Starting revision: `ccf6435`.

## Findings

- The first Vercel `/api/health` and `/api/cases` requests returned HTML 502 responses. The configured Singapore Render API initially timed out, then recovered. Subsequent requests through both Render and Vercel returned 200. This was a transient backend availability failure, not a broken SPA route.
- The guided batch action did not show request failures inside the guide. Its shared API client had no request deadline and converted the proxy's HTML error page into the unhelpful message `request failed`.
- On the scoreboard step, clicking “See the metrics” a second time after returning to the top did not scroll to metrics because the route/hash had not changed. Reproduced on production with the target still below the viewport after the second click.
- The floating guide covered part of the reviewer panel and had no minimize control.

## Fixes

- Show batch, reset, tracking and per-case investigation failures within the guide.
- Bound API requests to 30 seconds, explain proxy/network failures, and warn that a timed-out action may still be running. Mutating requests are not automatically repeated.
- Scroll on every metrics action and wait for receipt loading before restoring a dashboard hash target.
- Allow the guide to minimize and resume at the same step; constrain its height on short viewports.
- Describe lost progress without asserting that every polling failure means the server restarted.

## Verification

- Production build passed.
- All 61 component/hook/API-client tests passed. The new regression tests failed before the fixes and passed afterward.
- All 30 Playwright workflow checks passed against an isolated, freshly seeded copy of the current application.
- The isolated workflow covered the 10/16/6/4/4 outcome split; search and filters; the hero case's zero unexplained balance; evidence graph and trace; analyst approval and confirmation; blocked Probable/Conflicting/duplicate approvals; evidence requests; rejection confirmation; three distinct agent paths; audit verification and checkpoint download; tamper detection; reset and repeatability; guide navigation, repeated metrics navigation, minimize/resume; unknown routes/cases; dark mode; and phone layout/menu/guide behavior.
- Production was also exercised manually through all seven guide steps: introduction, demo batch, hero case, comparison, blocked Probable approval, audit verification and scoreboard. The batch completed 30 investigations; the live chain verified 570 events and one signed checkpoint. Per-case audit filtering and the signed checkpoint download worked.

Commands: `npm run build`, `npm test`, and `BASE_URL=http://127.0.0.1:8001 CHROMIUM_PATH=<installed Chromium executable> npm run e2e:workflow` from `web/`.

## Limits

Tampering, resets and review decisions were tested against the isolated copy, not against the public shared demo. Live-model execution was not tested. The frontend changes provide bounded failure and recovery feedback; they do not remove Render cold starts or other backend outages.
