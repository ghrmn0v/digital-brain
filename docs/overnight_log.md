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
