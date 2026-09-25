import test from "node:test";
import assert from "node:assert/strict";

import { describeSound } from "../src/sound.js";
import { STATE_SPEC } from "../src/animations.js";

test("every state sound in the animation spec has a synth preset", () => {
  for (const [state, spec] of Object.entries(STATE_SPEC)) {
    if (!spec.sound) continue;
    const preset = describeSound(spec.sound);
    assert.ok(preset, `${state} references unknown sound "${spec.sound}"`);
    for (const note of preset) {
      assert.ok(note.f > 0, `${state} note has no frequency`);
      assert.ok(note.dur > 0, `${state} note has no duration`);
    }
  }
});

test("state sounds match the backend state machine", () => {
  assert.equal(STATE_SPEC.IMPORTANT.sound, "soft_chime");
  assert.equal(STATE_SPEC.SUCCESS.sound, "success");
  assert.equal(STATE_SPEC.WARNING.sound, "chime");
  assert.equal(STATE_SPEC.ERROR.sound, "error");
  assert.equal(STATE_SPEC.IDLE.sound, undefined);
});

test("unknown sound names resolve to null", () => {
  assert.equal(describeSound("bogus"), null);
  assert.equal(describeSound(""), null);
  assert.equal(describeSound(undefined), null);
});

test("presets are arrays of frequency notes", () => {
  const success = describeSound("success");
  assert.ok(Array.isArray(success));
  assert.ok(success.length >= 3, "success should be a rising arpeggio");
  assert.ok(success[2].f > success[0].f, "success should rise in pitch");
});