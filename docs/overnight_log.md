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
