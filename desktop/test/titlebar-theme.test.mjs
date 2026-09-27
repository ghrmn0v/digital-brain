/**
 * The window controls must never paint a rectangle the app cannot see.
 *
 * The bug this pins: the frameless overlay shipped a hardcoded near-black
 * background, so in light mode the minimize / maximize / close buttons sat in a
 * black block against a light titlebar. The two things that must never come back
 * are that hardcoded colour and a fixed glyph colour, so both are asserted
 * directly rather than inferred from a screenshot.
 *
 * The subtler half is *whose* theme wins. This machine's OS is set to dark while
 * the app renders light, so a glyph colour taken from the OS preference paints
 * near-white controls on a white titlebar: no black block, but invisible buttons.
 * The app's own `data-theme` is therefore the source of truth, and these tests
 * hold it to that.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  OVERLAY_HEIGHT,
  READ_PAGE_THEME,
  THEME_POLL_MS,
  TRANSPARENT,
  followPageTheme,
  titleBarOverlayFor,
  windowBackgroundFor,
} from "../src/titlebar-theme.mjs";

/** A colour dark enough to read as a block rather than a glyph. */
function isDark(hex) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.3;
}

test("the overlay paints nothing, in either theme", () => {
  for (const dark of [true, false]) {
    const overlay = titleBarOverlayFor(dark);
    assert.equal(
      overlay.color,
      TRANSPARENT,
      `theme dark=${dark} must not paint an overlay background`,
    );
    assert.match(overlay.color, /^#[0-9a-f]{8}$/i);
    assert.equal(overlay.color.slice(7), "00", "alpha must be fully transparent");
  }
});

test("the old hardcoded overlay colours are gone", () => {
  for (const overlay of [titleBarOverlayFor(false), titleBarOverlayFor(true)]) {
    assert.notEqual(overlay.color.toLowerCase(), "#09090b");
    assert.notEqual(overlay.color.toLowerCase(), "#000000");
  }
  assert.notEqual(titleBarOverlayFor(false).symbolColor.toLowerCase(), "#a1a1aa");
});

test("glyphs contrast with the surface behind them", () => {
  const light = titleBarOverlayFor(false);
  const dark = titleBarOverlayFor(true);
  // On a light app background the symbols must be dark, and vice versa.
  assert.ok(isDark(light.symbolColor), `light symbols ${light.symbolColor} too light`);
  assert.ok(!isDark(dark.symbolColor), `dark symbols ${dark.symbolColor} too dark`);
  assert.equal(light.symbolColor, "#18181b");
  assert.equal(dark.symbolColor, "#f4f4f5");
});

test("light and dark are genuinely different, not one shared colour", () => {
  assert.notEqual(titleBarOverlayFor(true).symbolColor, titleBarOverlayFor(false).symbolColor);
});

test("the reserved overlay height is unchanged", () => {
  assert.equal(titleBarOverlayFor(true).height, OVERLAY_HEIGHT);
  assert.equal(titleBarOverlayFor(false).height, 44);
});

test("the pre-paint window background follows the theme", () => {
  assert.equal(windowBackgroundFor(true), "#09090b");
  assert.equal(windowBackgroundFor(false), "#ffffff");
});

test("the page is asked for a theme, and only for that", () => {
  assert.equal(READ_PAGE_THEME, 'document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"');
  assert.ok(!/localStorage|fetch|require|ipc/i.test(READ_PAGE_THEME), "the read must stay a plain attribute read");
});

/** Minimal stand-ins so the wiring is tested without booting Electron. */
function fakeWindow({ pageTheme = "light" } = {}) {
  const calls = [];
  const listeners = new Map();
  const state = { pageTheme, destroyed: false, readable: true };
  return {
    calls,
    state,
    isDestroyed: () => state.destroyed,
    on(event, fn) {
      listeners.set(event, [...(listeners.get(event) ?? []), fn]);
    },
    off(event, fn) {
      listeners.set(event, (listeners.get(event) ?? []).filter((f) => f !== fn));
    },
    emit(event) {
      for (const fn of listeners.get(event) ?? []) fn();
    },
    listenerCount(event) {
      return (listeners.get(event) ?? []).length;
    },
    setTitleBarOverlay(options) {
      calls.push(options);
    },
    setPageTheme(next) {
      state.pageTheme = next;
    },
    webContents: {
      isDestroyed: () => state.destroyed,
      executeJavaScript(expression) {
        if (state.destroyed || !state.readable) return Promise.reject(new Error("unavailable"));
        if (expression !== READ_PAGE_THEME) {
          return Promise.reject(new Error(`unexpected expression: ${expression}`));
        }
        return Promise.resolve(state.pageTheme);
      },
    },
  };
}

/** Let the pending poll promise chain drain. */
const settle = () => new Promise((r) => setTimeout(r, 0));

test("the page's theme wins over the OS preference", async (t) => {
  const window = fakeWindow({ pageTheme: "light" });
  t.after(
    followPageTheme({
      window,
      frameless: true,
      // The OS prefers dark; the app renders light. This is the real mismatch.
      nativeTheme: { shouldUseDarkColors: true },
      platform: "linux",
    }),
  );
  await settle();

  const last = window.calls.at(-1);
  assert.equal(last.color, TRANSPARENT);
  assert.equal(
    last.symbolColor,
    "#18181b",
    "a light page must get dark glyphs even though the OS prefers dark",
  );
});

test("a page that renders dark gets light glyphs", async (t) => {
  const window = fakeWindow({ pageTheme: "dark" });
  t.after(
    followPageTheme({
      window,
      frameless: true,
      nativeTheme: { shouldUseDarkColors: false },
      platform: "linux",
    }),
  );
  await settle();

  const last = window.calls.at(-1);
  assert.equal(last.color, TRANSPARENT);
  assert.equal(last.symbolColor, "#f4f4f5");
});

test("flipping the app theme repaints the controls", async (t) => {
  const window = fakeWindow({ pageTheme: "light" });
  t.after(
    followPageTheme({ window, frameless: true, nativeTheme: { shouldUseDarkColors: true }, platform: "linux" }),
  );
  await settle();
  const before = window.calls.length;

  window.setPageTheme("dark");
  window.emit("focus");
  await settle();

  assert.ok(window.calls.length > before, "the change must reach the overlay");
  assert.equal(window.calls.at(-1).symbolColor, "#f4f4f5");
  assert.equal(window.calls.at(-1).color, TRANSPARENT);
});

test("an unchanged theme does not keep repainting", async (t) => {
  const window = fakeWindow({ pageTheme: "light" });
  t.after(
    followPageTheme({ window, frameless: true, nativeTheme: { shouldUseDarkColors: false }, platform: "linux" }),
  );
  await settle();
  const after = window.calls.length;

  window.emit("focus");
  await settle();
  window.emit("focus");
  await settle();

  assert.equal(window.calls.length, after, "the same theme must not re-apply the overlay");
});

test("a page that cannot be read yet leaves a usable colour standing", async (t) => {
  const window = fakeWindow();
  window.state.readable = false;
  t.after(
    followPageTheme({ window, frameless: true, nativeTheme: { shouldUseDarkColors: true }, platform: "linux" }),
  );
  await settle();

  const last = window.calls.at(-1);
  assert.equal(last.color, TRANSPARENT, "still transparent before the page answers");
  assert.equal(last.symbolColor, "#f4f4f5", "falls back to the OS preference");
});

test("no polling is started when there is no overlay to colour", async () => {
  const window = fakeWindow();
  const stops = [
    // Native chrome: no overlay exists.
    followPageTheme({ window, frameless: false, nativeTheme: { shouldUseDarkColors: false }, platform: "linux" }),
    // macOS draws its own traffic lights.
    followPageTheme({ window, frameless: true, nativeTheme: { shouldUseDarkColors: false }, platform: "darwin" }),
    // No window yet.
    followPageTheme({ window: null, frameless: true, nativeTheme: { shouldUseDarkColors: false }, platform: "linux" }),
  ];
  await settle();
  for (const stop of stops) assert.doesNotThrow(stop);
  assert.equal(window.calls.length, 0, "nothing to colour means nothing painted");
  assert.equal(window.listenerCount("focus"), 0);
});

test("the disposer stops the polling", async () => {
  const window = fakeWindow();
  const stop = followPageTheme({ window, frameless: true, nativeTheme: { shouldUseDarkColors: false }, platform: "linux" });
  await settle();
  const after = window.calls.length;

  stop();
  window.setPageTheme("dark");
  window.emit("focus");
  await settle();

  assert.equal(window.calls.length, after, "a disposed watcher must go quiet");
  assert.equal(window.listenerCount("focus"), 0);
});

test("a window destroyed mid-flight is not touched", async () => {
  const window = fakeWindow();
  const stop = followPageTheme({ window, frameless: true, nativeTheme: { shouldUseDarkColors: false }, platform: "linux" });
  await settle();
  const after = window.calls.length;

  window.state.destroyed = true;
  window.emit("focus");
  await settle();
  stop();

  assert.equal(window.calls.length, after);
});

test("the poll interval is short enough to feel immediate", () => {
  assert.ok(THEME_POLL_MS <= 2000, `poll interval ${THEME_POLL_MS}ms is too slow to feel live`);
});
