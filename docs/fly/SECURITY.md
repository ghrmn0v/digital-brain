# Security audit — Fly / Connectome

Date: 26 Sep 2026. Scope: this subsystem only. Local-first, so the threat model
is a hostile or buggy network peer and untrusted message content, not the public
internet.

## Dependency audit

`npm audit` in `desktop/` reports **2 high-severity chains**, both rooted in
Electron `^33.0.2` (the installed tree is not present in this checkout, so the
audit was resolved from the lockfile):

| Package | Severity | Advisories |
|---|---|---|
| `electron` | high (many) | context isolation bypass, `contextBridge` prototype setters, `window.open` feature handling, sandboxed iframe popups/protocols, DevTools embedder and dock injection, permission-handler origin, off-screen rendering geometry, HTTP redirect into the local file loader |
| `extract-zip` | high | unvalidated symlink path traversal, arbitrary file writes via symlink archive entries |

`npm audit fix --force` proposes `electron@44.4.5`, a jump of eleven major
versions. **That was not applied**, and the reasoning is recorded below.

### Why the upgrade was not applied blindly

The exposure was assessed before deciding:

- `contextIsolation: true` and `nodeIntegration: false` are already set.
- The window loads **only** `index.html` from disk via `loadFile`. There is no
  `loadURL`, no `<webview>`, no remote origin anywhere in the app.
- The preload bridge exposes two inert values: `platform` and version strings.
- Most listed advisories concern features this app does not use: extension tabs,
  off-screen rendering, cross-origin iframes, autofill, permission handlers for
  embedded frames, and DevTools embedding.

So the realistic exposure is the two context-isolation and `contextBridge`
advisories, which apply because the bridge *is* used. Fixing them means a major
Electron upgrade, and an eleven-major jump cannot be validated here: the Node
test suite does not launch Electron, and there is no display. Shipping an
unverifiable major upgrade of the one component that renders the product is a
worse outcome than a documented, mitigated, known-version exposure.

**Recommended follow-up:** upgrade Electron to a current major in a session that
can actually launch the app and click through the flight cycle and the SSE
stream, with `npm test` and the smoke path as the gate.

### `extract-zip`

Transitive, install-time only: it extracts the Electron binary at install. The
archive is Electron's own download, not attacker-supplied, and it is not used at
runtime. Risk here is low; it is fixed by the same Electron upgrade.

## Code findings

### Fixed: latent XSS sink in the toast

`showToast` writes `innerHTML`, because messages carry styled spans. Its inputs
include values from the local backend response (`result.fetch`,
`result.reward_value`). Those are enums and numbers today, so **nothing is
currently exploitable** — but in a renderer that has a preload bridge, a backend
that ever echoed free-form text into `fetch` would turn this into script
execution. Every backend-supplied value is now escaped, and a test pins it.

The genuinely external path — a WhatsApp message body and sender name — already
used `textContent` and was left alone. That was correct and is now covered by a
test so it cannot regress.

### Fixed: shell hardening

`setWindowOpenHandler` denies all window opens, `will-navigate` blocks any
non-`file:` target, and `will-attach-webview` is refused. `webSecurity` and
`allowRunningInsecureContent: false` are now explicit rather than defaulted.
None of this fixes a CVE; it removes the preconditions most of the listed
advisories need, and it fails closed.

## Not verified

- **Java backend:** PARTIAL. No JDK or Maven in this environment, so the Spring
  service cannot be compiled or tested. Its test sources are reviewed statically
  only. A previous session with a JDK reported 57 passing tests; that result is
  historical and is not claimed as current.
- **Electron runtime behaviour:** NOT AVAILABLE. The app was not launched; the
  security assertions are source-level and unit-level.
- **`npm audit` for the Product and Brain:** see the repository-level report.
  Product is clean. The Brain is Python and has no equivalent lockfile-scoped
  scanner configured here.
