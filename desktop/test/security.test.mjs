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
  assert.match(main, /setWindowOpenHandler\(\(\)\s*=>\s*\(\{\s*action:\s*"deny"\s*\}\)\)/);
  assert.match(main, /on\("will-navigate"/);
  assert.match(main, /on\("will-attach-webview"/);
});

test("the shell keeps the core web guarantees explicit", () => {
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /webSecurity:\s*true/);
  assert.match(main, /allowRunningInsecureContent:\s*false/);
});

test("the shell only loads a local file and never a remote URL", () => {
  assert.ok(!/loadURL\(\s*["']https?:/.test(main), "shell must not load remote content");
  assert.match(main, /loadFile\(/);
});
