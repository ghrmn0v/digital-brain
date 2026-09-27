# Overnight Quality & UI/UX Loop

One entry per task. `PASS` means the full verification suite stayed green and the
change was committed. `REVERTED` means it broke something and was rolled back —
those entries are kept deliberately, because knowing what does not work is part
of the record.

Verification run after every change:

```
npm run build
npx tsc --noEmit
npm run lint
npx vitest run
.venv/bin/python -m pytest tests/ -q
```

Protected paths, never modified: `contracts/schemas/`, `contracts/api/schema.py`,
`.env`. Nothing is ever pushed to a remote.

## Task 0 — baseline: finish the interrupted Chat feature

- **Files:** `src/app/api/chat/route.ts` (new), `src/app/chat/page.tsx` (new),
  `src/components/connectome/chat-panel.tsx` (new),
  `src/components/connectome/chat-view.tsx` (new),
  `src/components/connectome/context-nav.tsx`,
  `src/components/connectome/connectome-inspector.tsx`,
  `src/components/connectome/connectome-workspace.tsx`,
  `src/components/dashboard-shell.tsx`
- **Result:** PASS
- **Notes:** The session began with five files of uncommitted, half-finished Chat
  work. Committing it as the first act avoids starting a refactor loop on top of
  a broken tree, and it compiles, lints and passes before anything else changed.

## Task 1 — audit for AI-wrapper clichés

- **Result:** audit only, no code change
- **Findings:** the brief's assumptions did not hold, and it is worth recording
  why. `purple|fuchsia|pink|violet|indigo`: **0** occurrences.
  `border-white/10`: **0**. Glow shadows: only **2**, both in `ui.tsx`.
  `rounded-2xl`: 15 across the app, which is moderate rather than bloated.
- **The real finding:** 17 hardcoded hex values (`#04070f`, `#060a14`, …) spread
  over five files. The Connectome ground was `#04070f`, the dashboard's
  `#020617`, the brand mark's `#09090B` — three near-blacks, each decided in a
  different file. That is the actual mechanism by which two shells came to look
  like two products. No amount of restyling individual components fixes it.

## Task 2 — one token layer instead of scattered hex

- **Files:** `src/components/connectome/theme.ts` (rewritten),
  `src/components/connectome/connectome-canvas.tsx`,
  `src/components/connectome/connectome-workspace.tsx`,
  `src/components/connectome/chat-view.tsx`,
  `src/components/connectome/chat-panel.tsx`
- **Result:** PASS
- **Notes:** `palette` and `surface` are now the only place a colour is decided.
  The palette is near-monochrome — surfaces step in small luminance increments,
  borders are one hairline step above their surface, and cyan appears only for
  intelligence, selection and focus. Graph node kind is carried by stroke, fill
  and an inner mark rather than by hue, which is what stops the map turning into
  a category chart. All 14 scattered hex literals in the components are gone; the
  only hex left is the token definitions themselves and one doc comment that
  records where the old values came from.

## Task 3 — remove glow shadows and card-radius bloat

- **Files:** `src/components/ui.tsx`,
  `src/components/dashboard-shell.tsx`,
  `src/components/connectome/chat-panel.tsx`,
  `src/components/connectome/command-bar.tsx`,
  `src/app/(dashboard)/error.tsx`
- **Result:** PASS
- **Notes:** All three glow shadows are gone — the cyan bloom on the primary
  button, the deep drop shadow on every `Panel`, and the halo behind the brand
  mark. Each was carrying weight without separating anything: a flat accent plus
  a hairline border does the same job more quietly, and on a page with several
  CTAs a glowing one out-shouts the content next to it. `Panel` and six repeated
  cards also stepped down from `rounded-2xl` to `rounded-xl`, so a list of
  related items reads as a list rather than a stack of tiles.

## Task 4 — Connectome workspace reads as one full-bleed surface

- **File:** `src/components/connectome/connectome-workspace.tsx`
- **Result:** PASS
- **Notes:** The two side panels were a lighter tint over the ground, which drew
  a visible seam down each side of the map and made the graph look like a box
  inside a frame. They now sit on the same ground, so the map runs edge to edge
  behind them and they read as floating panels. Structural dividers were kept —
  a layout does need them — but dropped from `/70` to `/50`, which is enough to
  separate surfaces that differ by almost nothing in luminance. Verified by
  screenshot at 1440, 768 and 390 before committing, not assumed.

## Task 5 — Chat answers stop showing raw Markdown

- **Files:** `src/components/connectome/chat-panel.tsx`,
  `src/components/connectome/chat-panel.test.ts`
- **Result:** PASS
- **Notes:** A live reply came back as `**Planning Meeting:** tomorrow at 10`,
  and the asterisks were rendered as literal characters. The model was writing
  Markdown and the UI was showing it as source. `renderInlineMarkdown` now
  handles the two markers the Brain's prompt actually asks for — `**bold**` and
  `` `code` `` — and returns React elements, so nothing is ever handed to
  `dangerouslySetInnerHTML`. The parser is deliberately small: it splits on the
  markers and emits `null` for an unclosed or empty one instead of inventing a
  repair, which is why `**unclosed` degrades to visible text rather than
  swallowing the rest of the sentence.

  Only the first pass is applied, so a marker inside a code span is not
  re-interpreted. Escaping is inherited from React's own text-node handling, and
  that is now asserted rather than assumed: the test feeds the renderer a
  `<script>` tag and an `<img onerror>` and requires both to still be markup in
  the output. A test that only checked for the presence of `<strong>` would have
  passed just as happily against a `dangerouslySetInnerHTML` implementation.

  The live check was inconclusive on purpose. Gemini was rate-limited during it,
  so the reply came from `context-only` and contained no markers to format. The
  fallback rendered honestly, which is the behaviour Task 5 is not about, so
  rather than retry until the quota came back and call a lucky screenshot
  "verified", the fix is pinned by five direct unit tests over the parser
  itself. `renderInlineMarkdown` is exported for that reason and for no other.

## Task 6 — one neutral scale across both shells

- **Files:** 32 files under `src/` (every component and route)
- **Result:** PASS
- **Notes:** `theme.ts` claimed "Tailwind classes use the zinc scale for type and
  borders". That was aspirational, not descriptive: 30 of the 32 files under
  `src/` were still `slate-*`, with `zinc-*` in only three. The two shells
  therefore still differed — the dashboard ground was `#020617`, a blue-tinted
  near-black, against the Connectome's neutral `#09090B`. That is exactly the
  "two shells look like two products" problem the token file was written to
  solve, and it survived Tasks 2 to 4 because those touched the Connectome.
  All 534 colour tokens are now `zinc-*`, so the ground, borders and muted text
  across the app are one neutral ramp and the only hue left is the cyan accent.

  The rewrite is mechanical but was not safe to do with a plain string replace,
  for a reason worth writing down: `translate-x` *contains* the substring
  `slate-`. `grep -c slate-` therefore reports nine hits that are not colours at
  all, and `sed s/slate-/zinc-/g` turns `translate-x-[1.4rem]` into
  `transzinc-x-[1.4rem]` — in the switch thumb, the skip link and two hover
  transforms. The replacement uses a negative lookbehind, `(?<!tran)`, and the
  run asserts that `translate` survives at its original count and that
  `transzinc` appears nowhere, rather than trusting the substitution.

  One scare worth recording: mid-run the generated stylesheet appeared to
  contain no `zinc` at all, which would have meant the earlier zinc work was
  dead classes. It was a stale `.next/dev` chunk from before those commits. The
  freshly built CSS holds 180 `zinc` references and no `slate` colour utility
  (the 33 remaining `slate` matches are the `translate` custom properties). This
  is the same stale-dev-build that made `next dev` screenshots untrustworthy
  earlier, and the reason verification here is done against `next start`.

  Verified by screenshot at 1440 and 390 on Dashboard, Connectome and Chat
  rather than by reading the diff.

## Task 7 — the last two decorative glows

- **Files:** `src/components/ai-operations-panel.tsx`,
  `src/components/integration-boundary.tsx`
- **Result:** PASS
- **Notes:** Task 3 removed the glow *shadows* but missed the glow *blobs* — two
  `absolute` circles of `bg-cyan-400/[0.07] blur-3xl` parked in the top-right
  corner of the AI operations panel and the integration boundary panel, one on
  the dashboard and one on Memory and People. They are the same decoration
  wearing a different property, and at `/[0.06]` they were faint enough to read
  as a rendering artifact rather than a choice, which is worse than not having
  them. Both are gone, and with them the `relative` that existed only to anchor
  them; `overflow-hidden` stays, since it still clips content to the panel's
  rounded corners.

  The five named shadows that remain (`shadow-lg` on the skip link, `shadow-2xl`
  on the mobile drawer, `shadow-sm` on a control) are deliberately kept. Those
  are elevation, not glow: an overlay needs to read as floating above the page
  behind it, and removing them would leave the drawer flush with its backdrop.

## Task 8 — the ground was still the old blue

- **Files:** `src/app/globals.css`, `src/app/layout.tsx`, `src/components/ui.tsx`
- **Result:** PASS
- **Notes:** Task 6 rewrote every `slate-*` utility and the dashboard still had a
  blue cast, because the page background never came from a utility. `body` takes
  `background: var(--background)`, and `--background` was `#020617` — slate-950,
  the exact value Task 6 was supposed to eliminate. Token classes cannot reach a
  custom property, so a grep for `slate-` reported a clean tree while the single
  largest surface in the product was untouched. The lesson generalises: the
  token sweep was only complete for the places a class can reach.

  Four more slate values were living in the same non-utility layer: the page
  ground and foreground vars, the four `::-webkit-scrollbar` colours, the
  `themeColor` in the viewport export (which is what a phone's browser chrome
  paints, so it was the last blue thing a user would see), and the select
  chevron, which is a `linear-gradient` literal in `selectClassName` and so had
  to be hand-edited rather than rewritten. All are now on the token palette.
  The chevron also moved from `#64748b` to `#a1a1aa`, which is not only the
  right neutral but is legible — at 4.0:1 the old grey was close to invisible
  against a `zinc-950/70` field.

  Verified by grepping the built stylesheet for the old hexes (zero) and
  screenshotting the dashboard against the rebuilt ground.

## Task 9 — the muted text was failing WCAG AA

- **Files:** `src/app/globals.css`, `src/components/connectome/theme.ts`,
  and every component using `text-zinc-500` / `text-zinc-600` (88 and 54
  occurrences)
- **Result:** PASS
- **Notes:** Measuring the neutral ramp against this app's actual composited
  grounds — a `zinc-900/55` panel over `zinc-950`, and a `zinc-950/55` card over
  that panel — `zinc-500` reaches only 4.0:1 and `zinc-600` only 2.5:1. Both
  fail WCAG AA, which needs 4.5:1 for text under 18px, and between them they
  carried every caption, every stat-card label and every uppercase section
  heading in the product, most of them at 10-12px, which is exactly the size
  that gets no large-text allowance.

  The obvious fix — promote both to `zinc-400` — would have passed and cost the
  design its hierarchy, leaving body copy, captions and section labels all at
  one weight. Tailwind's scale has no step between `zinc-400` (7.6:1) and
  `zinc-500` (4.0:1), so the fix was to insert the two missing tiers into the
  scale: `zinc-450` at `#8e8e99` and `zinc-550` at `#7e7e8a`, landing at 6.0:1
  and 4.8:1. Every caption and label moves up one tier in brightness and the
  ramp keeps three distinguishable steps, so the UI still reads as a dim
  monochrome product rather than brightening into a different one.

  The values are declared once in `globals.css` next to the other theme
  variables and mirrored in `theme.ts`, which is what the SVG canvas and
  anything in a style object use. The two files are kept in agreement by
  comment rather than by a build step, which is a real fragility worth knowing
  about: nothing fails if they drift.

## Task 10 — repair drifted indentation in the dashboard shell

- **File:** `src/components/dashboard-shell.tsx`
- **Result:** PASS
- **Notes:** 84 lines in this file had drifted out of alignment — the navigation
  array sat two spaces right of column zero, two of its three elements were
  indented differently from the first, the `Brand` link had a stray attribute
  indent, and the `.map()` body and the top-bar labels were each off by their
  own amount. It is the file every dashboard page renders inside, and it is
  where the permanent Overview / Connectome / Chat navigation lives, so the cost
  of reading it wrong is paid on every visit.

  Nothing in the toolchain was catching this: there is no Prettier in the
  project, the ESLint config sets no formatting rules, and the drift was
  syntactically valid throughout, so build, types, lint and all 90 tests passed
  with the file in this state. Whitespace that no tool checks is whitespace no
  one maintains.

  The corrections are applied as per-line shifts and the run asserts that every
  touched line has the same stripped content as before, so the change cannot be
  anything but whitespace. `git diff -w` on the file is empty, which is the
  proof worth keeping: 84 insertions and 84 deletions with no semantic delta.
  Rendering was re-checked by screenshot anyway, since JSX text nodes are
  whitespace-sensitive and a careless shift in a text line would compile
  cleanly and still change what a user reads.

## Task 11 — one drawer hook, and a real focus trap on the dashboard

- **Files:** `src/components/use-drawer.ts` (new),
  `src/components/use-drawer.test.ts` (new),
  `src/components/connectome/connectome-workspace.tsx`,
  `src/components/dashboard-shell.tsx`
- **Result:** PASS
- **Notes:** The Connectome drawers had a proper focus trap; the dashboard drawer
  set `aria-modal="true"` and then only moved focus in on open and back to the
  toggle on close. Tab from the last nav item walked out into the page the user
  could not see, so the attribute promised a containment the keyboard did not
  deliver. Rather than copy the trap across, the behaviour moved to
  `useDrawer` and both shells call it — one implementation, so the next drawer
  inherits it by default.

  Two defects were fixed in the course of that, both invisible to the type
  checker. The dashboard's `<aside>` had no `tabIndex`, so the hook's fallback
  for "no focusable child" targeted an element that cannot receive focus. And
  the existing hook took `close` as a dependency while every caller passed an
  inline arrow, so the effect tore down and re-ran on *every* render — and its
  cleanup restores focus to the toggle, meaning any re-render while a drawer was
  open would yank the user back to the first item mid-navigation. `close` is now
  read through a ref and kept out of the dependency list.

  The trap is unit-tested by extracting the only part with real logic in it,
  `wrapFocus`, as a pure function of `(focusable, active, shiftKey)`. That was
  forced by the environment rather than chosen for elegance: the suite runs in a
  node environment with no jsdom, and installing one is not on the table, so
  anything touching `document.activeElement` or real layout could only ever be
  checked by hand. The return value distinguishes "wrap to this" from "leave
  the event alone", which is the part worth pinning — calling `preventDefault`
  unconditionally would break Tab for every element in the middle of the list.

  Verified end to end, not just by unit test. Node 26 ships a global
  `WebSocket`, so the DevTools Protocol was driven directly with no new
  dependency: at 390x844 both drawers were opened, focus confirmed inside, then
  21 Tab and 3 Shift+Tab presses dispatched. Focus never left the panel in
  either direction (`insideDrawer` true for every step), Escape closed the
  drawer, focus returned to the toggle that opened it, and the body scroll lock
  was released. The Connectome drawer was re-checked the same way after the
  refactor (20 tabbables, 23 presses, no escape) to confirm the extraction did
  not regress the shell that already worked.

## Task 12 — a UI check that can actually fail

- **File:** `scripts/ui-check.mjs` (new)
- **Result:** PASS
- **Notes:** The suite runs in a node environment with no jsdom, so nothing in it
  can see whether a page renders, whether a client fetch fails, or whether a
  drawer holds focus. Those are the failures that matter in a UI and the ones a
  type checker will never mention. Every interactive check so far this session
  was a hand-driven throwaway, which is exactly the kind of verification that
  quietly stops being run.

  The script drives a real Chrome over the DevTools Protocol using Node's
  built-in global `WebSocket`, so it needs no new dependency and no browser
  automation library. It checks all 17 routes for console errors, uncaught
  exceptions and failed requests, and asserts each one renders real content
  rather than an empty shell; then it opens both mobile drawers and presses Tab
  and Shift+Tab through them, checking focus never leaves, Escape closes, the
  body scroll lock is released and focus lands back on the toggle. It exits
  non-zero on failure so it can be used as a gate.

  Two things had to be got right for the results to mean anything. Failures are
  recorded only after the page has gone idle: requests still in flight when the
  next navigation starts are aborted *by* that navigation, and an early version
  reported sixteen healthy routes as broken with `net::ERR_ABORTED` — a fault in
  the harness, not the app. And a check that cannot fail is not a check, so the
  trap was deliberately broken (`const target = null`) and the script re-run: it
  failed with `focus escaped on Tab #17` on the dashboard and `#19` on the
  Connectome, exit 1. Restored, rebuilt, green again.

  The route sweep also produced the first full-page baseline for the product, and
  it is clean: 17 routes, no console errors, no exceptions, no failed requests.
  Two harness bugs were found and fixed while writing it, both my own — parsing
  a value that `returnByValue` had already turned into an object, and only
  patching two of five identical call sites.

## Task 13 — Permissions access matrix and the dashboard hero dead gap

- **Files:** `src/lib/access-status.ts` (new),
  `src/lib/access-status.test.ts` (new),
  `src/components/permissions-status.tsx` (new),
  `src/app/(dashboard)/permissions/page.tsx`,
  `src/components/ai-operations-panel.tsx`
- **Result:** PASS
- **Notes:** `/permissions` rendered 262 characters of real content — a single
  policy table over an almost-empty database, on the one page where someone
  arriving worried about access has the least to look at. It now leads with an
  access status matrix covering the four things actually worth checking: local
  storage, the Gemini environment, the Brain transport, and the workspace's own
  policy mix. 262 characters became 2019.

  Every value is observed, not asserted. Storage does a real row-counting read
  and reports reachable or not; the Brain does a live `GET /health` behind a
  2.5s timeout so a slow Brain is a reported fact rather than a hanging page;
  the policy numbers come from the same records the table below renders. The
  derivation is split from the observation — `deriveAccessStatus` is pure and
  covered by 15 tests, which is only possible because nothing in it touches a
  database, a socket or `process.env`.

  The Gemini row is the one worth reading twice. The credential belongs to the
  Core Brain, so Product reports only that it is held elsewhere and that the
  Brain was pointed at an environment file; it never opens that file to find out
  more. A test asserts no detail or value string can match a credential-shaped
  token, because this is precisely the page someone opens while wondering
  whether they have been exposed. A missing Brain is reported as "not
  configured" rather than as a fault: for a local-first tool that is a normal
  state, and collapsing it into "broken" would train people to ignore the row.

  The first version of the health probe reported the Brain as unreachable with
  `HTTP 404` on a Brain that was up and serving. `CORE_BRAIN_URL` is the address
  of the `POST /v1/brain` method endpoint, not the server root, so appending
  `/health` asked for `/v1/brain/health`. The probe now resolves against the
  URL's origin and reports `digital-brain` on API `v1`. Caught by screenshot
  review rather than by a test — no test covered the URL shape, which is a gap
  worth remembering.

  The hero's dead band came from `lg:items-center` over three cards roughly half
  the height of the text column, so the leftover space was split above and below
  them. From `lg` the cards are now three full-width rows sharing the column
  height exactly (`lg:grid-rows-3` against `lg:items-stretch`) and switch to a
  horizontal layout, because a 480px row is too wide for a stacked
  number-over-label — which also stopped the third caption wrapping onto two
  lines. Three cards across is kept below `lg`, where the column is the full page
  width and a row is all they can be. The three cards are now one `stats` array
  instead of three hand-copied blocks, so they cannot drift apart again.

## Task 14 — the Electron PC shell, pointed at the product

- **Files:** `desktop/src/main.js`, `desktop/src/origin-policy.mjs` (new),
  `desktop/test/origin-policy.test.mjs` (new),
  `desktop/test/security.test.mjs`, `desktop/package.json`,
  `desktop/package-lock.json`, `desktop/README.md` (new)
- **Result:** PASS
- **Notes:** The shell existed but had never run here, and two things stopped it
  dead. `desktop/node_modules` did not exist, and once installed the Electron
  *binary* was still missing: the postinstall extracted exactly one file and
  stopped. The cause is a genuine bug in Electron's installer — a download
  rejection whose error object has an empty `.stack` is passed to
  `console.error(err.stack)`, so it prints two blank lines and exits `0`. Anyone
  trusting the exit code would conclude the install worked. `electron --version`
  is the only honest check, and the README now says so. The archive itself was
  fine, so it was extracted with the system `unzip` rather than by adding a
  dependency to work around a broken extractor.

  Electron 33.4.11 then had to go: `npm audit` reported **35 high-severity
  advisories**, including a context-isolation bypass, an HTTP-redirect-followed
  -into-local-file bug, and a service-worker spoof of `executeJavaScript` IPC
  replies. Those matter far more once the renderer is showing web content
  instead of a local file, so this was raised to 44.4.5, which audits clean.

  The main change is that the shell now loads `http://localhost:3000`, which
  invalidates a security invariant the suite asserted: `the shell only loads a
  local file and never a remote URL` forbade any `loadURL("http…")`. Deleting
  that assertion would have quietly removed a real guarantee, so it is restated
  as something stronger — the loaded target must be a loopback host on an allowed
  port, and a hardcoded remote origin is still fatal. The allowlist itself lives
  in `origin-policy.mjs` as a pure function with 14 tests, including that a host
  which merely *resolves* to `127.0.0.1` is refused, because that answer can
  change between the check and the request. A second old assertion pinned one
  exact arrow shape for the `window.open` denial; it now asserts the denial
  itself, since the handler legitimately grew a parameter.

  The web app is loaded with **no preload and no Node access at all**. The Fly
  page keeps its bridge, but a renderer showing web content has no reason to hold
  one, and the smallest bridge is the one with least to get wrong. Device
  permissions are denied outright, and off-origin links open in the real browser
  instead of turning the window into one.

  Verified by launching, not by reading the diff. Smoke mode reported
  `SMOKE_LOADED http://localhost:3000/dashboard` — the `/` → `/dashboard`
  redirect is in-app routing, so its being allowed rather than blocked is direct
  evidence the origin policy permits navigation while refusing to leave the
  origin. A `grim` capture of the real Hyprland desktop confirmed the frameless
  window draws working minimise/maximise/close overlay controls, which was the
  real risk in choosing frameless: a compositor that ignored `titleBarOverlay`
  would leave no way to close the window. `CEREBRO_WINDOW_CHROME=native` is the
  documented escape hatch.

  `npm start` pins `--ozone-platform=x11` because Chromium's Vulkan backend is
  incompatible with the Wayland Ozone hint on this desktop. 44 tests pass.

## Task 15 — tell a spent quota apart from a rate limit, and stop showing slugs

- **Files:** `core/understanding/gemini.py`,
  `core/service/brain_service.py`,
  `src/components/connectome/chat-panel.tsx`,
  `tests/test_gemini_provider.py`, `tests/test_brain_service.py`,
  `src/components/connectome/chat-panel.test.ts`
- **Result:** PASS
- **Notes:** Measured against the provider rather than inferred from the log: the
  key is valid, and the free tier allows **5 requests per minute** for
  `gemini-3.8-flash`, after which Google answers `429 RESOURCE_EXHAUSTED` with
  `quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier` and an
  explicit `retryAfter: 57s`. Five probes returned 200 and the next three were
  429 — exactly the cap.

  Every 429 was being reported as `gemini rate limit reached`, which sends an
  operator looking for a transient problem that clears by itself. This one does
  not clear: only billing or a slower request rate does. `_http_error` now reads
  the 429 body and names the window from a fixed table, so the reason reads
  `gemini quota exhausted (per-minute limit)`. Only a window *name* is lifted out
  of the payload — never body text, which can echo the request back — and a test
  asserts a secret planted in the body cannot reach the message or the usage log.

  Writing that test uncovered a second bug that would have made the feature
  pointless. A 429 is retryable, so `_post` raises the *same* `HTTPError` object
  twice, and an `HTTPError` is a one-shot stream: the second attempt read an empty
  body and downgraded the precise diagnosis straight back to "rate limit". Since
  every 429 is retried, the specific message would never have survived to the
  caller. The window is now memoised on the exception, which makes the function
  idempotent and is not merely an optimisation.

  `_fallback_slug` cut the provider detail at a hard `[:40]`, producing
  `…does not support oper` — mid-word, with nothing marking it as cut, so it read
  like a bug in the message. It now collapses whitespace, cuts on a word
  boundary and appends `…`. The limit moved from 40 to **48** for a reason worth
  recording: the longest reason the Gemini provider produces is `gemini quota
  exhausted (per-minute limit)` at 41 characters, so a limit of 40 truncated away
  the one detail that says *which* window was hit. The bound exists to stop
  arbitrary provider text running away, not to squeeze Core's own vocabulary, and
  a test pins every reason the provider can raise.

  The chat panel was appending the raw slug to the visible sentence. Telemetry
  is not prose, so `describeFallbackReason` now translates it and the slug is kept
  as a `title` tooltip — available to someone debugging, invisible to everyone
  else. Patterns are matched against the whole slug because the detail after the
  colon is provider text, quota is matched before the generic rate limit because a
  quota slug also contains the word "limit", and an unrecognised slug returns
  `null` so the panel says nothing rather than inventing a cause.

  Verified in a real browser with the quota deliberately exhausted: the banner
  reads "The AI provider's quota for this model is used up.", `provider_unavailable`
  does not appear anywhere in the rendered text, and the span's `title` holds the
  full slug.

## Task 16 — move the demo data to usr_demo, and stop retrying a quota we were told to wait out

- **Files:** `core/understanding/gemini.py`, `tests/test_gemini_provider.py`,
  and the local `.demo/brain.sqlite3` (gitignored, so not in the commit)
- **Result:** PASS
- **Notes:** The user id change in Task 15 orphaned the demo data — all eight
  memories, three ingestion receipts and one learning-state row belonged to
  `usr_integration_test`, so `usr_demo` started empty and Chat answered "I do
  not have any stored information". Migrated in a single transaction after
  stopping the Brain and checkpointing the WAL, with a copy of the database
  (plus `-wal` and `-shm`) kept at
  `/tmp/opencode/brain.sqlite3.pre-migration`. Worth noting that the main
  database file was 4 KB with all 321 KB of data in the write-ahead log, so
  editing it while the Brain held it open would have been the wrong move.
  Verified through the Brain API, not just with SQL: the hackathon question
  grounds three memories under `usr_demo`, and a broader one reaches four facts.

  Google tells us how long to wait and we were not listening. Every 429 body
  carries `RetryInfo.retryDelay` — `57.05s` against the free tier's per-minute
  cap — and the module discarded it, sleeping a fixed 1.5 s and retrying once.
  That retry cannot succeed: the window has not reopened. It cost a request,
  added the backoff to the caller's latency, and returned the same 429.
  `_retry_would_be_wasted` now reads the delay and skips the retry when it
  exceeds five seconds. The ceiling is a ceiling and not a target: honouring a
  57-second hint by sleeping 57 seconds would move the problem into the request
  path, so the ceiling is on skipping, not on waiting.

  The hint is read from `RetryInfo.retryDelay` in the body *and* from a standard
  `Retry-After` header, because providers use both, and a duration is accepted as
  `"57.05s"`, `"2s"`, `"3"`, or a bare number. The 5-second boundary is exact:
  `5s` still retries, `5.1s` does not.

  Body parsing moved into one memoised `_QuotaFacts` record, because the window
  and the delay arrive together and the previous per-field helpers each wanted a
  read. Memoisation is load-bearing rather than tidy — `HTTPError` is a one-shot
  stream, and `_post` raises the same object twice, so anything not remembered
  from the first attempt is gone on the second. That was the Task 15 bug, and
  adding the delay to the same record would otherwise have reintroduced it.

  Measured rather than assumed: with the quota deliberately exhausted, a chat
  returns in **0.40 s** instead of the ~1.9 s the unconditional backoff cost, and
  the reason still names the window — `provider_unavailable:gemini quota
  exhausted (daily limit)`, the daily cap having been reached during testing.

## Task 17 — Connectome readability and palette harmony

- **Files:** `src/components/connectome/labels.ts`,
  `src/components/connectome/labels.test.ts`,
  `src/components/connectome/theme.ts`
- **Result:** PASS
- **Notes:** Asked to adopt the `product` branch as the UI baseline and discard
  the components it replaced. `product` is an **ancestor** of `main`: the merge
  base is product's own tip, `git merge product` reports "Already up to date",
  and main is 77 commits ahead of it — product's tip is dated 2026-09-26 03:27
  against main's 2026-09-27 12:13. Adopting it would have deleted 28 files that
  exist only on main, including `src/app/connectome/`, all of
  `src/components/connectome/`, the entire Chat feature and the permissions
  matrix — the very components the same instruction said to preserve. Nothing was
  merged or discarded; the merge was verified as a no-op and the work went into
  the Connectome instead.

  The real defect was label truncation. Every label was cut at 25 characters
  regardless of how much room the node had, so a node beside 300px of empty
  canvas still read "Ayxan will bring the hack…". `placeLabels` now walks a
  ladder — full length, then 44, 34, 26 — and keeps the longest variant that
  finds a free slot, so the room decides. Cuts land on a word boundary and carry
  an ellipsis. The existing collision logic is unchanged: labels still avoid each
  other *and* the node discs, and a label with nowhere to go is still not drawn.

  Two things about that ladder are worth recording because the tests found them.
  A label that is one unbroken 53-character token has no boundary to cut on, so
  the cut is hard and the ellipsis is the only thing marking it — the test
  asserts the mark rather than pretending a boundary exists. And "Principal
  Engineer, hackathon…" shortens to "Principal Engineer…", so the character after
  the kept text is the comma that was then stripped; asserting a space there
  failed twice before the contract was stated correctly.

  The palette now matches the design system's own rule. `theme.ts` has claimed
  that node kind is carried by shape and ring weight "not by hue", while the code
  used indigo `#A5B4FC` for proposals and a cyan-tinted fill and `#CFFAFE` text
  for threads — the one hue on the map belonging to no palette. Proposals are the
  Brain's own output, so they read on the single cyan accent like every other
  intelligence node, with the heavier ring carrying the distinction. Every
  off-ramp value is gone from both `nodeStyles` and `edgeStyles`.

  Checked rather than assumed: two fresh loads of `/connectome` are
  byte-identical (`compare -metric AE` → 0), so the map still does not reshuffle,
  which is the property the force suite pins.
