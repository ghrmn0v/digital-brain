import { app, BrowserWindow, Menu, shell } from "electron";
import fs, { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  DEFAULT_PORT,
  isAllowedUrl,
  resolveMode,
  resolveTarget,
  safeOrigin,
  TargetError,
} from "./origin-policy.mjs";

/**
 * The Cerebro Flow desktop shell.
 *
 * It opens the same web interface the browser gets, on this machine, and adds
 * the things a browser tab cannot: a real application window, an in-app
 * accelerator set, and a window that survives being closed and reopened.
 *
 * Two decisions are worth stating up front.
 *
 * The shell loads a *web origin*, not a local file. That changes the security
 * question from "is this remote" to "can this be made to leave the machine", so
 * the allowlist is a literal loopback host on an explicitly permitted port and
 * nothing else — see `origin-policy.mjs`, which is where the rules and their
 * tests live. A host that merely resolves to 127.0.0.1 is still refused, because
 * that answer can change between the check and the request.
 *
 * Hotkeys are registered with `before-input-event` rather than
 * `globalShortcut`. A global shortcut is a system-wide claim on a key
 * combination, which for a local single-window app is a poor trade: it silently
 * takes the key away from every other application, and on a shared desktop it
 * can collide with something the user cannot see. Scoped accelerators do the
 * same job for the person actually using the window.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
// Packaged builds resolve assets from the app directory, so try the packaged
// location first and fall back to the repository checkout for `npm start`.
const iconPath = [
  path.join(app.getAppPath(), "..", "public", "brand", "cerebro-flow-icon.png"),
  path.join(here, "..", "..", "public", "brand", "cerebro-flow-icon.png"),
].find((candidate) => existsSync(candidate)) ?? undefined;

const config = {
  mode: resolveMode(process.env.CEREBRO_SHELL_MODE),
  target: process.env.CEREBRO_APP_URL,
  ports: (process.env.CEREBRO_ALLOWED_PORTS ?? String(DEFAULT_PORT))
    .split(",")
    .map((port) => Number(port.trim()))
    .filter((port) => Number.isInteger(port) && port > 0),
  frameless: (process.env.CEREBRO_WINDOW_CHROME ?? "frameless") !== "native",
  devTools: process.env.CEREBRO_DEVTOOLS === "1",
  smoke: process.env.CEREBRO_SMOKE === "1",
};

const origin = safeOrigin(config.target, config.ports);
const flyMode = config.mode === "fly";

/** Reported once on startup so a misconfiguration is visible, not silent. */
function describeTarget() {
  if (flyMode) return "local Fly page";
  try {
    const resolved = resolveTarget(config.target, config.ports);
    if (resolved.origin !== origin) {
      return `${resolved.origin} (after falling back from an invalid value)`;
    }
    return resolved.origin;
  } catch (error) {
    const reason = error instanceof TargetError ? error.message : "unknown reason";
    return `${origin} (configured value rejected: ${reason})`;
  }
}

/**
 * Shown when the web server is not up.
 *
 * A blank window is the worst possible outcome here: it looks like a broken app
 * rather than a service that is not running, so the failure is rendered as a page
 * that says what to do. It is built as a document written by this process, never
 * by the renderer, and it carries no preload and no Node access.
 */
function offlineDocument(target) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'" />
    <title>Cerebro Flow — service unavailable</title>
    <style>
      :root { color-scheme: dark; }
      body {
        margin: 0; min-height: 100vh; display: grid; place-items: center;
        background: #09090b; color: #fafafa;
        font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      }
      main { max-width: 34rem; padding: 2.5rem; }
      h1 { font-size: 1.25rem; letter-spacing: -0.01em; margin: 0 0 0.75rem; }
      p { color: #a1a1aa; margin: 0 0 1rem; }
      code {
        display: block; background: #111113; border: 1px solid #27272a;
        border-radius: 0.75rem; padding: 0.9rem 1rem; color: #e4e4e7;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px;
        white-space: pre-wrap; word-break: break-word;
      }
      .row { display: flex; gap: 0.75rem; margin-top: 1.25rem; }
      button {
        font: inherit; font-size: 14px; cursor: pointer; border-radius: 0.75rem;
        padding: 0.6rem 1rem; border: 1px solid #3f3f46; background: #18181b; color: #fafafa;
      }
      button.primary { background: #22d3ee; border-color: #22d3ee; color: #09090b; font-weight: 600; }
    </style>
  </head>
  <body>
    <main>
      <h1>The Cerebro Flow web service is not responding</h1>
      <p>
        This window loads the product from <code style="display:inline;padding:0.1rem 0.35rem">${target}</code>.
        Nothing is wrong with the desktop app — the server it loads has not answered.
      </p>
      <code>cd digital-brain-main-integration
npm run build
npx next start -p 3000</code>
      <p>The Core Brain also has to be running for Chat and Connectome to answer: it listens on port 8765.</p>
      <div class="row">
        <button class="primary" onclick="location.reload()">Try again</button>
        <button onclick="window.cerebroRetry && window.cerebroRetry()">Recheck</button>
      </div>
    </main>
  </body>
</html>`;
}

let mainWindow = null;

/** Injected into the offline page only, so it has no preload and no Node. */
function attachOfflineBridge(contents) {
  contents.executeJavaScript(`
    window.cerebroRetry = () => window.location.reload();
    true;
  `).catch(() => {});
}

function createWindow() {
  const bounds = restoreBounds();

  const win = new BrowserWindow({
    ...bounds,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: "Cerebro Flow",
    // Without this the taskbar, the window manager and the Alt-Tab switcher all
    // fall back to Electron's default mark, so a launched app looks like a
    // generic dev window rather than Cerebro Flow.
    icon: iconPath,
    backgroundColor: "#09090b",
    // Frameless by default, with the platform's own window controls drawn over
    // the content. `native` is the escape hatch for compositors that do not
    // render the overlay, where a frameless window would have no way to close.
    ...(config.frameless
      ? {
          frame: false,
          titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "hidden",
          ...(process.platform === "darwin"
            ? {}
            : {
                titleBarOverlay: {
                  color: "#09090b",
                  symbolColor: "#a1a1aa",
                  height: 44,
                },
              }),
        }
      : {}),
    webPreferences: {
      // The Fly page needs its preload bridge. The web app needs no Node access
      // at all, so it gets none — the smaller the bridge, the less there is to
      // get wrong in a renderer that is now showing web content.
      ...(flyMode ? { preload: path.join(here, "preload.cjs") } : {}),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      spellcheck: false,
    },
  });

  mainWindow = win;

  // Nothing in this app needs a device permission, and a local page should not
  // be able to ask. Denying by default also removes a class of origin-confusion
  // bugs around permission requests from nested frames.
  win.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  win.webContents.session.setPermissionCheckHandler(() => false);

  // Deny window.open outright, and refuse any navigation that leaves the one
  // origin this shell is allowed to show. The failure mode is closed: an
  // unexpected link opens in the user's real browser instead of turning this
  // window into one.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:$/.test(safeProtocol(url))) shell.openExternal(url).catch(() => {});
    return { action: "deny" };
  });

  win.webContents.on("will-navigate", (event, url) => {
    const allowed = flyMode ? url.startsWith("file:") : isAllowedUrl(url, origin);
    if (!allowed) {
      event.preventDefault();
      if (/^https?:$/.test(safeProtocol(url))) shell.openExternal(url).catch(() => {});
    }
  });

  win.webContents.on("will-attach-webview", (event) => event.preventDefault());

  // A load that fails is the common case here — the web server simply is not up
  // yet — so it is answered with an explanation rather than left blank.
  win.webContents.on("did-fail-load", (_event, code, description, url, isMainFrame) => {
    if (!isMainFrame) return;
    // -3 is ABORTED, which a normal in-app navigation also produces.
    if (code === -3) return;
    showOffline(win, `${code} ${description}`, url);
  });

  win.webContents.on("render-process-gone", (_event, details) => {
    console.error("renderer gone:", details.reason);
  });

  win.webContents.on("unresponsive", () => console.error("renderer unresponsive"));
  win.webContents.on("responsive", () => console.error("renderer responsive again"));

  registerAccelerators(win);

  win.once("ready-to-show", () => {
    win.show();
    if (config.devTools) win.webContents.openDevTools({ mode: "detach" });
  });

  win.on("close", () => rememberBounds(win));
  win.on("closed", () => {
    if (mainWindow === win) mainWindow = null;
  });

  if (flyMode) {
    win.loadFile(path.join(here, "index.html"));
  } else {
    win.loadURL(origin);
  }

  if (config.smoke) attachSmoke(win);
  buildMenu();
  return win;
}

function safeProtocol(url) {
  try {
    return new URL(url).protocol;
  } catch {
    return "";
  }
}

function showOffline(win, reason, failedUrl) {
  console.error(`load failed (${reason}) for ${failedUrl}`);
  const html = offlineDocument(origin);
  win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`).catch(() => {});
  win.webContents.once("did-finish-load", () => attachOfflineBridge(win.webContents));
  win.webContents.once("did-fail-load", () => {});
}

/** Window geometry survives a restart, which is most of what "graceful" means here. */
function boundsFile() {
  return path.join(app.getPath("userData"), "window-bounds.json");
}

function restoreBounds() {
  try {
    const saved = JSON.parse(fs.readFileSync(boundsFile(), "utf8"));
    if (Number.isInteger(saved.width) && Number.isInteger(saved.height)) {
      return { width: saved.width, height: saved.height, x: saved.x, y: saved.y };
    }
  } catch {
    // No saved bounds yet, or unreadable. Defaults are fine.
  }
  return { width: 1280, height: 860 };
}

function rememberBounds(win) {
  try {
    const { width, height, x, y } = win.getNormalBounds();
    fs.writeFileSync(boundsFile(), JSON.stringify({ width, height, x, y }));
  } catch {
    // Losing the geometry is not worth interrupting a close for.
  }
}

function registerAccelerators(win) {
  win.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown" || !input.control) return;
    const key = input.key.toLowerCase();

    if (key === "r" && input.shift) {
      event.preventDefault();
      win.webContents.reloadIgnoringCache();
    } else if (key === "r") {
      event.preventDefault();
      win.webContents.reload();
    } else if (key === "i" && input.shift) {
      event.preventDefault();
      win.webContents.toggleDevTools();
    } else if (key === "=" || key === "+") {
      event.preventDefault();
      zoom(win, 0.1);
    } else if (key === "-") {
      event.preventDefault();
      zoom(win, -0.1);
    } else if (key === "0") {
      event.preventDefault();
      win.webContents.setZoomLevel(0);
    } else if (key === "q" && input.shift) {
      event.preventDefault();
      app.quit();
    }
  });
}

function zoom(win, delta) {
  const level = win.webContents.getZoomLevel();
  win.webContents.setZoomLevel(Math.min(5, Math.max(-5, level + delta)));
}

function buildMenu() {
  const template = [
    ...(process.platform === "darwin" ? [{ role: "appMenu" }] : []),
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    { role: "windowMenu" },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

/**
 * Headless verification hook: report what loaded, then exit.
 *
 * Used by the launch check so "the window opened the right thing" is an
 * observation rather than an assumption.
 */
function attachSmoke(win) {
  win.webContents.on(
    "console-message",
    // Electron 37 replaced the positional (event, level, message) signature
    // with a single event object. Both are handled so this works across the
    // versions the package range allows.
    (...args) => {
      const last = args.at(-1);
      const message =
        typeof last === "object" && last !== null && "message" in last
          ? `${last.level}: ${last.message}`
          : args.slice(1).join(" ");
      console.log(`[renderer] ${message}`);
    },
  );
  win.webContents.on("did-finish-load", () => {
    const url = win.webContents.getURL();
    console.log(`SMOKE_LOADED ${url}`);
    setTimeout(async () => {
      // Optional proof that the window painted the app rather than a blank
      // surface. Captured from inside the app, so it needs no screenshot tool.
      if (process.env.CEREBRO_SMOKE_SHOT) {
        try {
          const image = await win.webContents.capturePage();
          fs.writeFileSync(process.env.CEREBRO_SMOKE_SHOT, image.toPNG());
          console.log(`SMOKE_SHOT ${process.env.CEREBRO_SMOKE_SHOT}`);
        } catch (error) {
          console.error("SMOKE_SHOT_FAILED", error);
        }
      }
      try {
        const title = await win.webContents.executeJavaScript("document.title");
        const h1 = await win.webContents.executeJavaScript(
          "document.querySelector('h1')?.textContent?.trim() ?? ''",
        );
        console.log(`SMOKE_TITLE ${title}`);
        console.log(`SMOKE_H1 ${h1}`);
        console.log("CEREBRO_SMOKE_OK");
      } catch (error) {
        console.error("SMOKE_PROBE_FAILED", error);
      }
      app.exit(0);
    }, 2500);
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    console.error("SMOKE_CRASH", details.reason);
    app.exit(1);
  });
}

// One window per launch: a second `npm start` focuses the first instead of
// opening a rival instance that fights over the same ports and userData.
//
// A smoke run is deliberately exempt. It is a verification, not a launch, and
// the case that matters most is checking a build while the app is already open
// — which is exactly when the lock would hand back a silent exit 0 and no
// output at all, so the check would appear to pass without having run.
if (config.smoke || app.requestSingleInstanceLock()) {
  if (!config.smoke) {
    app.on("second-instance", () => {
      if (!mainWindow) return;
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    });
  }

  app.whenReady().then(() => {
    console.log(`Cerebro Flow shell starting; target ${describeTarget()}`);
    createWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

    app.on("window-all-closed", () => {
      if (process.platform !== "darwin") app.quit();
    });
} else {
  // Say so rather than exiting silently, so "nothing happened" is never a
  // mystery: the window is already open and has just been raised.
  console.log("Cerebro Flow is already running — focusing the existing window.");
  app.quit();
}

