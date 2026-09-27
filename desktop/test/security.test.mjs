import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

/**
 * The renderer runs with a preload bridge, so an injected script is not a
 * cosmetic problem. Toast messages are authored as HTML so they can carry styled
 * spans, which means every interpolated *value* has to be escaped.
 *
 * These tests check the contract rather than a running DOM: the renderer is a
 * plain script with no module exports, so it is inspected as source. That is
 * weaker than a behavioural test, so the assertions are deliberately specific
 * about the exact interpolations that carry backend data.
 */

const here = dirname(fileURLToPath(import.meta.url));
const renderer = readFileSync(join(here, "..", "src", "renderer.js"), "utf8");
const main = readFileSync(join(here, "..", "src", "main.js"), "utf8");

test("toast escaping helper covers the dangerous characters", () => {
  const match = renderer.match(/function esc\(value\)\s*\{[\s\S]*?\n\}/);
  assert.ok(match, "esc() helper not found");
  for (const char of ["&", "<", ">", '"', "'"]) {
    assert.ok(
      match[0].includes(char),
      `esc() does not handle ${char}`,
    );
  }
});

test("every backend-supplied toast value is escaped", () => {
  // Checked as literal source text rather than by pattern, because the safe
  // interpolations are indistinguishable by shape from the unsafe ones:
  // `sign`, `n` and the two `result.flight` ternaries all reduce to literals we
  // author (a sign glyph, a key count, "ON"/"OFF"), so a clever regex would only
  // produce false positives. These are the values that can carry text from
  // outside the renderer.
  for (const expr of ["result.fetch", "result.reward_value", "feedback"]) {
    assert.ok(
      renderer.includes("${esc(" + expr + ")}"),
      `${expr} should reach a toast escaped, but no escaped interpolation was found`,
    );
    assert.ok(
      !renderer.includes("${" + expr + "}"),
      `${expr} is interpolated into toast HTML without escaping`,
    );
  }
});

test("no toast interpolates a raw value straight from a response object", () => {
  // Catches a future call site that forgets to escape, without flagging the
  // literals we author ourselves.
  for (const match of renderer.matchAll(/\$\{(result\.[a-zA-Z_.]+)\}/g)) {
    assert.fail(`unescaped response value in a toast: \${${match[1]}}`);
  }
});

test("message bodies and sender names are never written as HTML", () => {
  // The external-content path: a WhatsApp body or sender name is untrusted.
  assert.ok(
    !/bubble\.querySelector\("\.(text|speaker)"\)\.innerHTML/.test(renderer),
    "bubble text/speaker must use textContent, not innerHTML",
  );
  assert.match(renderer, /\.querySelector\("\.text"\)\.textContent = context\.body_preview;/);
});

test("the shell denies navigation and window opens", () => {
  // Asserted as behaviour rather than as one exact arrow shape: the handler
  // now also forwards http(s) targets to the system browser, so it takes a
  // parameter, but it still must end in a deny.
  assert.match(main, /setWindowOpenHandler\(/);
  assert.match(main, /return\s*\{\s*action:\s*"deny"\s*\}/);
  assert.match(main, /on\("will-navigate"/);
  assert.match(main, /on\("will-attach-webview"/);
});

test("the shell keeps the core web guarantees explicit", () => {
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /webSecurity:\s*true/);
  assert.match(main, /allowRunningInsecureContent:\s*false/);
});

test("the shell only loads a loopback origin and never a remote host", () => {
  // This used to assert that the shell never loads an http URL at all. The
  // shell now loads the product's own web interface on this machine, so the
  // invariant is restated rather than dropped: the loaded target must be a
  // loopback host on an allowed port. A hardcoded remote origin is still fatal.
  assert.ok(
    !/loadURL\(\s*["']https?:\/\/(?!localhost|127\.0\.0\.1|\[::1\])/.test(main),
    "shell must not hardcode a remote origin",
  );
  assert.match(main, /loadURL\(\s*origin\s*\)/);
  // The allowlist itself is asserted behaviourally in origin-policy.test.mjs.
  assert.match(main, /isAllowedUrl\(\s*url\s*,\s*origin\s*\)/);
  assert.match(main, /import \{[^}]*isAllowedUrl[^}]*\} from "\.\/origin-policy\.mjs"/s);
  // The local Fly page is still reachable, but only as an explicit opt-in.
  assert.match(main, /loadFile\(/);
  assert.match(main, /CEREBRO_SHELL_MODE/);
});

test("the web app is loaded with no Node bridge at all", () => {
  // Loading a web origin means the renderer is no longer a local file, so the
  // preload bridge must not be attached to it. The Fly page keeps its preload;
  // the web app gets none.
  assert.match(main, /flyMode\s*\?\s*\{\s*preload:/);
  assert.match(main, /sandbox:\s*true/);
});

test("device permissions are denied by default", () => {
  // A local page should not be able to ask for a camera or a microphone, and
  // denying removes the nested-frame origin-confusion cases as well.
  assert.match(main, /setPermissionRequestHandler/);
  assert.match(main, /callback\(false\)/);
  assert.match(main, /setPermissionCheckHandler\(\(\)\s*=>\s*false\)/);
});

test("a smoke run is not swallowed by the single-instance lock", () => {
  // Regression guard. The lock is right for a second launch, but it made
  // `npm run smoke` exit 0 with no output whenever the app was already open —
  // so the check appeared to pass without having run, which is worse than not
  // having it.
  assert.match(main, /config\.smoke\s*\|\|\s*app\.requestSingleInstanceLock\(\)/);
});

test("a refused second launch says so instead of exiting silently", () => {
  // "Nothing happened" should never be a mystery: the window is already open.
  assert.match(main, /already running/);
  assert.match(main, /focusing the existing window/);
});

test("the shell degrades with an explanation when the web server is down", () => {
  assert.match(main, /on\("did-fail-load"/);
  assert.match(main, /offlineDocument/);
  assert.match(main, /CEREBRO_SMOKE_OK/);
});
