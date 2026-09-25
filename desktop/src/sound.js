// Tiny WebAudio synthesizer for fly state sounds. Tones are generated (no audio
// files to distribute); the note table is pure/exported for tests. AudioContext is
// created lazily and unlocked on the first user interaction (browser autoplay rule).

const SOUND_SPECS = {
  soft_chime: [
    { f: 523.25, t: 0.0, dur: 0.24 },
    { f: 659.25, t: 0.18, dur: 0.24 },
    { f: 783.99, t: 0.36, dur: 0.3 },
  ],
  chime: [
    { f: 659.25, t: 0.0, dur: 0.18 },
    { f: 880.0, t: 0.2, dur: 0.26 },
  ],
  success: [
    { f: 523.25, t: 0.0, dur: 0.12 },
    { f: 659.25, t: 0.1, dur: 0.12 },
    { f: 1046.5, t: 0.2, dur: 0.3 },
  ],
  error: [
    { f: 174.61, t: 0.0, type: "sawtooth", dur: 0.28 },
    { f: 130.81, t: 0.06, type: "sawtooth", dur: 0.3 },
  ],
};

export function describeSound(name) {
  return name && Object.prototype.hasOwnProperty.call(SOUND_SPECS, name) ? SOUND_SPECS[name] : null;
}

let ctx = null;
let userInteracted = false;

function unlock() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC || userInteracted) return;
  tmpCtx();
  userInteracted = true;
}

function tmpCtx() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  if (!ctx) ctx = new AC();
  if (ctx.state === "suspended") {
    ctx.resume().then(() => {});
  }
  return ctx;
}

export function unlockAudio() {
  unlock();
}

export function playStateSound(name) {
  const spec = describeSound(name);
  if (!spec) return;
  const audio = tmpCtx();
  if (!audio) return;
  const now = audio.currentTime;
  for (const note of spec) {
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = note.type || "sine";
    osc.frequency.value = note.f;
    const start = now + (note.t || 0);
    const dur = note.dur || 0.22;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.12, start + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    osc.connect(gain);
    gain.connect(audio.destination);
    osc.start(start);
    osc.stop(start + dur + 0.05);
  }
}