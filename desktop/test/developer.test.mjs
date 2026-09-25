import test from "node:test";
import assert from "node:assert/strict";

import { resolveDeveloperBubble, anchorFor, DEFAULT_BUBBLE_MS } from "../src/developer.js";

const MESSAGE = "user may be undefined before accessing user.email";

function devContext(overrides = {}) {
  return {
    developer: {
      type: "developer.bug_detected",
      event_id: "dev_evt_1",
      repository: "companion-app",
      file: "src/auth/login.ts",
      line: 42,
      column: 10,
      title: "Possible null reference",
      message: MESSAGE,
      severity: "warning",
      anchor: "code_2",
      mapped: true,
      bubble_ms: 9000,
      ...overrides,
    },
  };
}

test("returns null without a developer envelope", () => {
  assert.equal(resolveDeveloperBubble(null), null);
  assert.equal(resolveDeveloperBubble({}), null);
});

test("Brain-provided message is displayed verbatim", () => {
  const bubble = resolveDeveloperBubble(devContext());
  assert.equal(bubble.text, MESSAGE);
});

test("bubble respects the backend-provided duration", () => {
  assert.equal(resolveDeveloperBubble(devContext()).durationMs, 9000);
});

test("bubble falls back to default duration when bubble_ms is absent", () => {
  const bubble = resolveDeveloperBubble(devContext({ bubble_ms: undefined }));
  assert.equal(bubble.durationMs, DEFAULT_BUBBLE_MS);
});

test("speaker carries uppercased severity and title", () => {
  assert.equal(resolveDeveloperBubble(devContext()).speaker, "WARNING · Possible null reference");
});

test("title falls back to the event type", () => {
  const bubble = resolveDeveloperBubble(devContext({ title: undefined }));
  assert.equal(bubble.speaker, "WARNING · developer.bug_detected");
});

test("severity is upper-cased for the speaker label", () => {
  const bubble = resolveDeveloperBubble(devContext({ severity: "Warning" }));
  assert.equal(bubble.speaker, "WARNING · Possible null reference");
});

test("meta renders repository/file/line/column", () => {
  assert.equal(resolveDeveloperBubble(devContext()).meta, "companion-app / src/auth/login.ts:42:10");
});

test("meta is empty when location fields are missing", () => {
  const bubble = resolveDeveloperBubble(devContext({ repository: null, file: null, line: null, column: null }));
  assert.equal(bubble.meta, "");
});

test("anchorFor returns the backend anchor when present", () => {
  assert.equal(anchorFor(devContext()), "code_2");
});

test("anchorFor returns null when unmapped or missing", () => {
  assert.equal(anchorFor(devContext({ anchor: "attention_area" })), "attention_area");
  assert.equal(anchorFor(devContext({ anchor: undefined })), null);
  assert.equal(anchorFor(devContext({ anchor: "" })), null);
  assert.equal(anchorFor(null), null);
});