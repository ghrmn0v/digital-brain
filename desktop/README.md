# Cerebro Flow desktop shell

The PC shell. It opens the same web interface you get at
`http://localhost:3000` in a real application window, with the window chrome,
accelerators and lifecycle a browser tab does not have.

The Fly / Connectome 3D visual layer still lives here too, as an explicit
opt-in mode. See [Modes](#modes).

## Requirements

The shell renders a web app, so the services have to be running first. From the
repository root:

```bash
npm run build
npx next start -p 3000          # the product
python -m core.transport.http --host 127.0.0.1 --port 8765 --db .demo/brain.sqlite3
node scripts/product-worker.mjs  # optional: automation and delivery ticks
```

If the web server is not up, the window does not go blank — it explains what is
missing and gives you a **Try again** button. That is deliberate: a blank window
looks like a broken app rather than a service that is not running.

## Install

```bash
cd desktop
npm ci
```

If `npm ci` finishes but `./node_modules/.bin/electron --version` reports
"Electron failed to install correctly", the postinstall that downloads the
Electron binary did not complete. Electron's installer swallows some download
failures — it logs an empty stack and exits `0` — so check for it explicitly
rather than trusting the exit code:

```bash
node node_modules/electron/install.js   # retry; safe to run again
./node_modules/.bin/electron --version   # must print a version
```

Still nothing? Extract the cached archive yourself and write the pointer file:

```bash
ZIP=$(ls ~/.cache/electron/*/electron-v*-linux-x64.zip | tail -1)
rm -rf node_modules/electron/dist && mkdir -p node_modules/electron/dist
unzip -q -o "$ZIP" -d node_modules/electron/dist
printf 'electron' > node_modules/electron/path.txt
chmod +x node_modules/electron/dist/electron
```

## Run

```bash
npm start                # the web app (default)
npm run start:fly        # the local Fly / Connectome 3D page
npm run devtools         # web app with DevTools open
npm run start:wayland    # native Wayland instead of XWayland
```

`npm start` uses `--ozone-platform=x11`. Chromium's Vulkan backend is not
compatible with the Wayland Ozone hint Electron picks up on Hyprland, and the
window logs a warning and falls back; XWayland is the reliable path on this
desktop. Use `start:wayland` on a compositor where Vulkan works.

## Verify

```bash
npm run build      # there is no transpile step, so this is validation
npm run validate   # same thing, named for what it does
npm test           # 44 tests
npm run smoke      # launches, loads the app, reports the title, exits
```

`smoke` is the useful one before a demo. It prints what it loaded and what the
page's `h1` is, so "the window opened the right thing" is an observation:

```
Cerebro Flow shell starting; target http://localhost:3000
SMOKE_LOADED http://localhost:3000/dashboard
SMOKE_TITLE Dashboard · Cerebro Flow
SMOKE_H1 Good focus starts with a clear system
CEREBRO_SMOKE_OK
```

Add `CEREBRO_SMOKE_SHOT=/tmp/shot.png` to also capture the window contents.

## Modes

| Mode | Command | Loads | Preload bridge |
|---|---|---|---|
| `web` (default) | `npm start` | `http://localhost:3000` | none |
| `fly` | `npm run start:fly` | `desktop/src/index.html` | `preload.cjs` |

The web app gets **no** preload and no Node access: the renderer is showing web
content, so the bridge is removed rather than left in place for something to
reach. The Fly page is a local file that has always needed its bridge, so it
keeps it.

## Configuration

All optional; every value is validated and a bad one is reported on startup
instead of being silently ignored.

| Variable | Default | Meaning |
|---|---|---|
| `CEREBRO_APP_URL` | `http://localhost:3000` | Where the web app is. Loopback only. |
| `CEREBRO_ALLOWED_PORTS` | `3000` | Comma-separated ports the shell may load. |
| `CEREBRO_SHELL_MODE` | `web` | `web` or `fly`. |
| `CEREBRO_WINDOW_CHROME` | `frameless` | `frameless` or `native`. |
| `CEREBRO_DEVTOOLS` | unset | `1` opens DevTools on start. |
| `CEREBRO_SMOKE` | unset | `1` self-exits after reporting what loaded. |
| `CEREBRO_SMOKE_SHOT` | unset | Path to write a PNG of the window. |

Set `CEREBRO_WINDOW_CHROME=native` if your compositor does not draw the
frameless overlay controls; without them a frameless window has no way to close.

## Keyboard

Scoped to the window, not the system. A global shortcut silently takes a key
combination away from every other application, which is a poor trade for a local
single-window app.

| Shortcut | Action |
|---|---|
| `Ctrl/Cmd + R` | Reload |
| `Ctrl/Cmd + Shift + R` | Reload, ignoring cache |
| `Ctrl/Cmd + Shift + I` | Toggle DevTools |
| `Ctrl/Cmd + +` / `-` / `0` | Zoom in / out / reset |
| `Ctrl/Cmd + Shift + Q` | Quit |
| `F11` | Full screen (also on the View menu) |

## Security model

The shell loads a **web origin**, which changes the question from "is this
remote" to "can this be made to leave the machine". `src/origin-policy.mjs` is
the whole boundary and is a pure function with its own tests:

- Only `http:` on a literal loopback host (`localhost`, `127.0.0.1`, `::1`) on an
  explicitly allowed port. A host that merely *resolves* to `127.0.0.1` is still
  refused, because that answer can change between the check and the request.
- Navigation is allowed anywhere inside that one origin, so in-app routing works,
  and refused everywhere else. Off-origin links open in the real browser rather
  than turning this window into one.
- `window.open` is denied. Webviews are denied. Device permissions are denied.
- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`,
  `webSecurity: true`.

One known warning: Electron logs an insecure-Content-Security-Policy notice for
the loaded page, because Next.js serves its bootstrap inline. Electron states the
notice does not apply once the app is packaged, and adding a strict CSP from the
shell would break Next's inline bootstrap, so it is left alone deliberately.

## Packaging

There is no packaging toolchain installed, and adding one is a deliberate step
rather than something to do quietly. To produce installers:

```bash
cd desktop
npm install --save-dev electron-builder
npx electron-builder --linux AppImage deb     # or: --win nsis, --mac dmg
```

`electron-builder` needs `build` in `package.json` — `appId`, `files` and
`linux`/`win`/`mac` targets. Two things to decide first:

- The app has no bundler; the renderer is plain ES modules that Chromium loads
  directly, so `files` only needs `src/**`, `package.json` and `models/`.
- `models/` is 37 MB, dominated by `fly.png`. It is only needed in `fly` mode, so
  excluding it from the default package is a large saving if the web app is the
  only target.
