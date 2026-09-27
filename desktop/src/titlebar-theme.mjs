/**
 * Titlebar theming for the frameless shell.
 *
 * The window is frameless, so Chromium draws the platform's own minimize /
 * maximize / close buttons *over* our content via `titleBarOverlay`. That
 * overlay paints a background colour of its own, which is why the controls used
 * to sit in a hardcoded near-black rectangle: in light mode the app underneath
 * was light, and the overlay was not.
 *
 * Two rules follow from the app owning its own theme:
 *
 * 1. The overlay background is always fully transparent. The page already paints
 *    the correct background for the active theme, so the overlay must not paint
 *    one. A transparent overlay is theme-agnostic — it cannot disagree with the
 *    app, because it contributes nothing.
 * 2. Only the glyphs are ours to colour, and they must contrast with whatever is
 *    behind them. Dark glyphs on the light background, light glyphs on the dark
 *    one.
 *
 * The app's theme is a `data-theme` attribute on <html> that a person can flip
 * from the UI, and the main process cannot see it: the web renderer is
 * deliberately given no bridge (see the webPreferences block in main.js), so
 * there is no channel for the page to *push* a change.
 *
 * So the shell reads it instead. `webContents.executeJavaScript` runs in the
 * page's world but is called by the main process, not the page, which keeps the
 * web renderer with no Node access and no bridge of its own — the security
 * property that comment protects is untouched. A `data-theme` flip is the only
 * way the theme changes and it raises no event the main process can hear, so
 * the value is re-read on a timer; the expression is a single attribute read.
 */

/** Height reserved for the overlay, matching the app's own header. */
export const OVERLAY_HEIGHT = 44;

/** Fully transparent. Electron wants #rrggbbaa; 00 alpha paints nothing. */
export const TRANSPARENT = "#00000000";

/** How often the page theme is re-read, in ms. */
export const THEME_POLL_MS = 1000;

/** Read by the shell in the page's world. Kept tiny and side-effect free. */
export const READ_PAGE_THEME =
  'document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"';

/** Zinc-100: the glyphs the app uses for primary text on its dark background. */
const SYMBOL_ON_DARK = "#f4f4f5";

/** Zinc-900: the same role on the light background. */
const SYMBOL_ON_LIGHT = "#18181b";

/** Base window colour, shown only before the first paint of the page. */
const WINDOW_ON_DARK = "#09090b";
const WINDOW_ON_LIGHT = "#ffffff";

/**
 * The `titleBarOverlay` options for a theme.
 *
 * @param {boolean} dark whether the surrounding app is in dark mode
 * @returns {{color: string, symbolColor: string, height: number}}
 */
export function titleBarOverlayFor(dark) {
  return {
    color: TRANSPARENT,
    symbolColor: dark ? SYMBOL_ON_DARK : SYMBOL_ON_LIGHT,
    height: OVERLAY_HEIGHT,
  };
}

/**
 * The window's base background for a theme.
 *
 * @param {boolean} dark whether the surrounding app is in dark mode
 * @returns {string}
 */
export function windowBackgroundFor(dark) {
  return dark ? WINDOW_ON_DARK : WINDOW_ON_LIGHT;
}

/**
 * Follow the theme the page is actually rendering.
 *
 * `nativeTheme` only knows the OS preference, and the app does not have to agree
 * with it: the theme is a `data-theme` attribute a person can flip in the UI, and
 * this desktop session is a real case of the two disagreeing — the OS set to
 * dark while the app renders light, which with an OS-driven glyph colour leaves
 * the controls nearly invisible on a white titlebar.
 *
 * So the page is asked, and its answer wins. A failed read is not an error worth
 * surfacing: it means the page has not painted yet, or navigated away, and the
 * OS answer already on screen is a reasonable stand-in until the next tick.
 *
 * @param {object} options
 * @param {import("electron").BrowserWindow|null} options.window
 * @param {boolean} options.frameless whether this window uses the overlay
 * @param {{shouldUseDarkColors: boolean}} options.nativeTheme fallback before the page answers
 * @param {string} [options.platform] process.platform, for the mac check
 * @param {number} [options.intervalMs]
 * @returns {() => void} disposer
 */
export function followPageTheme({
  window,
  frameless,
  nativeTheme,
  platform,
  intervalMs = THEME_POLL_MS,
}) {
  if (!frameless || !window || platform === "darwin") return () => {};

  let applied = null;

  const apply = (dark) => {
    if (window.isDestroyed?.()) return;
    if (applied !== null && applied === dark) return;
    applied = dark;
    window.setTitleBarOverlay(titleBarOverlayFor(dark));
  };

  // Until the page answers, the OS preference is the best guess available.
  apply(nativeTheme.shouldUseDarkColors);

  let inFlight = false;
  const poll = async () => {
    if (inFlight || window.isDestroyed?.()) return;
    const contents = window.webContents;
    if (!contents || contents.isDestroyed?.()) return;
    inFlight = true;
    try {
      const answer = await contents.executeJavaScript(READ_PAGE_THEME, true);
      apply(answer === "dark");
    } catch {
      // Not ready, navigated away, or the window is going down. The colour
      // already on screen stands until the next tick.
    } finally {
      inFlight = false;
    }
  };

  void poll();
  const timer = setInterval(poll, intervalMs);
  // A forgotten disposer must never be able to hold a process open. Electron's
  // own loop keeps the app running regardless, so nothing is lost by the timer
  // not being a reason to stay alive.
  timer.unref?.();
  // A focused window is the one being looked at, so re-read on focus.
  window.on?.("focus", poll);

  return () => {
    clearInterval(timer);
    window.off?.("focus", poll);
  };
}
