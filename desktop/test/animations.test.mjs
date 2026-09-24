import test from "node:test";
import assert from "node:assert/strict";

import { STATE_SPEC, resolve, positionOf, POSITIONS } from "../src/animations.js";

test("every fly state from the backend has a visual spec", () => {
  const backendStates = [
    "IDLE", "BACKGROUND", "ATTENTION", "CURIOUS", "THINKING", "PROCESSING",
    "IMPORTANT", "WARNING", "SUCCESS", "ERROR", "WAITING", "SLEEPING",
    "LISTENING", "LEARNING",
  ];
  for (const name of backendStates) {
    assert.ok(STATE_SPEC[name], `missing visual spec for ${name}`);
  }
});

test("important state is bright, large and fast", () => {
  const spec = resolve("IMPORTANT");
  assert.equal(spec.visibility, "bright");
  assert.equal(spec.scale, 1.5);
  assert.equal(spec.speed, 0.9);
  assert.equal(spec.position, "attention_area");
  assert.equal(spec.duration_ms, 8000);
});

test("unknown state falls back to idle spec", () => {
  const spec = resolve("MADE_UP_STATE");
  assert.equal(spec.animation, "hover");
  assert.equal(spec.fallback, true);
});

test("sleeping is dim, small and grounded", () => {
  const spec = resolve("SLEEPING");
  assert.equal(spec.visibility, "dim");
  assert.equal(spec.position, "corner_low");
});

test("all positions resolve to 3D vectors", () => {
  for (const key of Object.keys(POSITIONS)) {
    const [x, y, z] = positionOf(key);
    assert.equal(typeof x, "number");
    assert.equal(typeof z, "number");
  }
});