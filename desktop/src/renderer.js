import * as THREE from "../node_modules/three/build/three.module.js";
import { resolve, positionOf } from "./animations.js";
import { resolveDeveloperBubble, anchorFor } from "./developer.js";
import { playStateSound, unlockAudio } from "./sound.js";

const WS_URL = "ws://127.0.0.1:8080/ws/fly";
const API_URL = "http://127.0.0.1:8080/api/v1";

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0f14);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 1.5, 7.0);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xffffff, 0.7));
const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
keyLight.position.set(3, 6, 4);
scene.add(keyLight);
const rimLight = new THREE.DirectionalLight(0x88ccff, 0.6);
rimLight.position.set(-4, 1, -3);
scene.add(rimLight);

const FLY_TEXTURE_URL = "../models/fly.png";

function buildFly(texture) {
  const group = new THREE.Group();

  if (texture) {
    const img = texture.image;
    const aspect = img && img.width && img.height ? img.width / img.height : 1;
    const height = 0.62;
    const width = height * Math.min(Math.max(aspect, 0.5), 2.2);
    const billboardMat = new THREE.MeshStandardMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(width, height), billboardMat);
    group.add(plane);
    group.userData = { materials: [billboardMat], billboard: true };
    return group;
  }

  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x2a2f35, roughness: 0.45, metalness: 0.2 });
  const glossy = new THREE.MeshStandardMaterial({ color: 0x3a4250, roughness: 0.25, metalness: 0.35 });

  const body = new THREE.Mesh(new THREE.SphereGeometry(0.16, 24, 24), bodyMat);
  body.scale.set(1, 0.8, 1.6);
  body.position.y = 0;
  body.castShadow = true;

  const thorax = new THREE.Mesh(new THREE.SphereGeometry(0.12, 20, 20), glossy);
  thorax.scale.set(0.9, 0.7, 1.1);
  thorax.position.set(0, 0.02, -0.32);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.1, 20, 20), glossy);
  head.scale.set(0.9, 0.8, 1.0);
  head.position.set(0, 0.01, -0.5);

  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x661122, roughness: 0.2, metalness: 0.6 });
  const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 16), eyeMat);
  eyeL.position.set(-0.07, 0.05, -0.46);
  const eyeR = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 16), eyeMat);
  eyeR.position.set(0.07, 0.05, -0.46);

  const wingMat = new THREE.MeshStandardMaterial({
    color: 0x9fd8ff,
    transparent: true,
    opacity: 0.55,
    side: THREE.DoubleSide,
    roughness: 0.5,
  });
  const wingShape = new THREE.Shape();
  wingShape.moveTo(0, 0);
  wingShape.absellipse(1.4, 0, 0.95, 0.5, 0, Math.PI);
  wingShape.absellipse(1.4, 0, 0.95, 0.5, Math.PI, Math.PI * 2);
  const wingGeo = new THREE.ShapeGeometry(wingShape);
  wingGeo.scale(0.16, 0.16, 0.16);

  const wingRoot = new THREE.Group();
  wingRoot.position.set(0, 0.04, -0.22);
  const wingL = new THREE.Mesh(wingGeo, wingMat);
  wingL.position.set(0.55, 0.05, 0);
  wingL.rotation.y = -0.35;
  const wingR = new THREE.Mesh(wingGeo, wingMat);
  wingR.position.set(-0.55, 0.05, 0);
  wingR.rotation.y = Math.PI + 0.35;
  wingRoot.add(wingL, wingR);

  const legMat = new THREE.MeshStandardMaterial({ color: 0x1a1e22, roughness: 0.8 });
  const legs = [];
  for (let i = 0; i < 3; i++) {
    const z = 0.15 - i * 0.22;
    for (const side of [-1, 1]) {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.3, 6), legMat);
      leg.position.set(side * 0.16, -0.2, z);
      leg.rotation.z = side * -0.5;
      legs.push(leg);
    }
  }

  const antennaMat = new THREE.MeshStandardMaterial({ color: 0x444c56 });
  const antennaL = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.22, 6), antennaMat);
  antennaL.position.set(-0.035, 0.1, -0.52);
  antennaL.rotation.x = -0.5;
  const antennaR = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.22, 6), antennaMat);
  antennaR.position.set(0.035, 0.1, -0.52);
  antennaR.rotation.x = -0.5;

  group.add(body, thorax, head, eyeL, eyeR, wingRoot, antennaL, antennaR, ...legs);
  group.userData = {
    body,
    wingRoot,
    wingL,
    wingR,
    legs,
    antennaL,
    antennaR,
    materials: [bodyMat, glossy, eyeMat, wingMat, legMat, antennaMat],
  };
  return group;
}

let fly = buildFly(null);
scene.add(fly);

new THREE.TextureLoader().load(
  FLY_TEXTURE_URL,
  (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    const textured = buildFly(texture);
    textured.position.copy(fly.position);
    textured.visible = fly.visible;
    scene.remove(fly);
    scene.add(textured);
    fly = textured;
  },
  undefined,
  () => {
    console.warn(`no fly image at ${FLY_TEXTURE_URL}, keeping primitive fly`);
  },
);

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(4.2, 48),
  new THREE.MeshStandardMaterial({ color: 0x141a21, roughness: 0.9 }),
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -1.4;
scene.add(floor);

const grid = new THREE.GridHelper(9, 18, 0x222a33, 0x181f27);
grid.position.y = -1.38;
scene.add(grid);

const runtime = {
  state: "IDLE",
  spec: resolve("IDLE"),
  until: Infinity,
  behaviorId: null,
  offline: false,
  anchor: null,
  lastSound: null,
  priorityLevel: "?",
  flightChain: [],
  pos: new THREE.Vector3(0, 0.3, 0),
};

const bubble = document.getElementById("speech-bubble");
let bubbleTimer = 0;

function showBubble(context) {
  if (!context || !context.body_preview) return;
  const speaker = context.sender_name || "unknown";
  bubble.querySelector(".speaker").textContent = speaker;
  bubble.querySelector(".text").textContent = context.body_preview;
  const meta = bubble.querySelector(".meta");
  if (meta) meta.textContent = "";
  bubble.style.display = "block";
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(hideBubble, 7000);
}

function showDeveloperBubble(context) {
  const resolved = resolveDeveloperBubble(context);
  if (!resolved) return;
  bubble.querySelector(".speaker").textContent = resolved.speaker;
  bubble.querySelector(".text").textContent = resolved.text;
  const meta = bubble.querySelector(".meta");
  if (meta) meta.textContent = resolved.meta;
  bubble.style.display = "block";
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(hideBubble, resolved.durationMs);
}

function hideBubble() {
  bubble.style.display = "none";
}

function positionBubble() {
  const head = new THREE.Vector3(fly.position.x, fly.position.y + 0.7, fly.position.z);
  head.project(camera);
  const x = (head.x * 0.5 + 0.5) * window.innerWidth;
  const y = (-head.y * 0.5 + 0.5) * window.innerHeight;
  bubble.style.left = `${Math.min(Math.max(x, 172), window.innerWidth - 172)}px`;
  bubble.style.top = `${Math.min(Math.max(y, 128), window.innerHeight - 24)}px`;
}

const hud = document.getElementById("hud");
const hudTag = document.getElementById("hud-tag");
const wsDot = document.getElementById("ws-dot");
const stateLabel = document.getElementById("state");

const toast = document.getElementById("toast");
let toastTimer = 0;
/**
 * Escape a value for interpolation into toast markup.
 *
 * `showToast` needs real HTML because messages carry styled spans, so the
 * markup is authored here and only ever *values* are escaped. Message bodies and
 * sender names already go through `textContent`; this closes the same door for
 * toasts, whose inputs come from the backend response. Today those are enums and
 * numbers, so nothing is exploitable — but a backend that ever echoes free-form
 * text into `fetch` or `flight` would otherwise turn this into script execution
 * inside a renderer that has a preload bridge.
 */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function showToast(html, cls = "") {
  toast.innerHTML = html;
  toast.className = cls ? `visible ${cls}` : "visible";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.className = "";
  }, 3200);
}

function playState(state) {
  const spec = resolve(state);
  runtime.state = state;
  runtime.spec = spec;
  runtime.anchor = null;
  if (spec.sound && spec.sound !== runtime.lastSound) {
    playStateSound(spec.sound);
    runtime.lastSound = spec.sound;
  }
  runtime.until = spec.duration_ms > 0 ? performance.now() + spec.duration_ms : spec.requires_ack ? Infinity : performance.now() + 60000;
  stateLabel.textContent = `${state} · ${(runtime.priorityLevel || "?").toLowerCase()}`;
}

function applyDecision(decision) {
  let state = decision.fetch || "IDLE";
  if (state === "FLYING") {
    runtime.flightChain = ["TAKEOFF", "FLYING", "LANDING"];
    state = "TAKEOFF";
  }
  runtime.behaviorId = decision.behavior_id || runtime.behaviorId;
  runtime.priorityLevel = decision.priorityLevel || "?";
  playState(state);
}

function applyDeveloperEvent(msg) {
  applyDecision({ ...msg.decision, behavior_id: msg.behavior_id });
  runtime.anchor = anchorFor(msg.context);
  const resolved = resolveDeveloperBubble(msg.context);
  if (resolved) {
    runtime.until = performance.now() + resolved.durationMs;
  }
  if (msg.context) showDeveloperBubble(msg.context);
}

function returnToIdle() {
  if (runtime.spec.requires_ack && performance.now() < runtime.until) {
    return;
  }
  if (runtime.flightChain.length) {
    playState(runtime.flightChain.shift());
    return;
  }
  runtime.state = "IDLE";
  runtime.spec = resolve("IDLE");
  runtime.anchor = null;
  runtime.lastSound = null;
  runtime.until = performance.now() + 1500;
  stateLabel.textContent = "IDLE";
  hideBubble();
}

function tickLoop() {
  requestAnimationFrame(tickLoop);
  const now = performance.now();
  const t = now / 1000;
  const spec = runtime.spec;
  const target = positionOf(runtime.anchor || spec.position);
  const ease = Math.min(1, spec.speed * 0.02);

  runtime.pos.x += (target[0] - runtime.pos.x) * ease;
  runtime.pos.y += (target[1] - runtime.pos.y) * ease;
  runtime.pos.z += (target[2] - runtime.pos.z) * ease;

  fly.visible = spec.visibility !== "hidden";
  const opacity = spec.visibility === "bright" ? 1.0 : spec.visibility === "normal" ? 0.85 : spec.visibility === "low" ? 0.55 : 0.4;
  for (const mat of fly.userData.materials) {
    if (mat.transparent) mat.opacity = opacity;
  }

  const baseScale = spec.scale;
  const flapRate = 8 + spec.speed * 14;
  const flapAmp = 0.35 + spec.speed * 0.45;
  if (fly.userData.wingL) {
    if (spec.animation === "perch" || spec.animation === "slow_pulse") {
      fly.userData.wingL.rotation.x = -1.0;
      fly.userData.wingR.rotation.x = 1.0;
    } else {
      fly.userData.wingL.rotation.x = -Math.sin(t * flapRate) * flapAmp;
      fly.userData.wingR.rotation.x = Math.sin(t * flapRate) * flapAmp;
    }
  }

  let extra = new THREE.Vector3();
  let squash = 1;
  switch (spec.animation) {
    case "hover":
      extra.y += Math.sin(t * 1.6) * 0.03;
      break;
    case "perch":
      squash = 1 + Math.sin(t * 1.1) * 0.05;
      fly.rotation.z = Math.sin(t * 0.9) * 0.02;
      break;
    case "drift":
      extra.x = Math.sin(t * 0.7) * 0.25;
      break;
    case "perk":
      extra.y = Math.max(0, Math.sin(t * 3.0)) * 0.15;
      fly.rotation.z = Math.sin(t * 2.5) * 0.12;
      break;
    case "tilt":
      fly.rotation.z = Math.cos(t * 2.0) * 0.3;
      break;
    case "hover_tilt":
      fly.rotation.z = Math.sin(t * 2.0) * 0.12;
      extra.y += Math.sin(t * 1.2) * 0.02;
      break;
    case "stutter": {
      const step = Math.floor(t * 2.2) % 2;
      extra.z = step === 0 ? 0.08 : -0.04;
      break;
    }
    case "spin":
      if (fly.userData.billboard) {
        fly.rotation.z = Math.sin(t * 2.0) * 0.2;
      } else {
        fly.rotation.y += spec.speed * 0.05;
      }
      break;
    case "pulse":
      squash = 1 + Math.sin(t * 3.0) * 0.12;
      break;
    case "zoom_alert":
      extra.z = Math.max(0, Math.sin(t * 3.5)) * 0.12;
      fly.rotation.z = Math.sin(t * 6.0) * 0.18;
      break;
    case "pacing":
      extra.x = Math.sin(t * 1.4) * 0.4;
      break;
    case "happy_bounce":
      extra.y = Math.abs(Math.sin(t * 6.0)) * 0.2;
      fly.rotation.z = 0;
      break;
    case "shake":
      extra.x = (Math.random() - 0.5) * 0.2;
      extra.y = (Math.random() - 0.5) * 0.2;
      break;
    case "falter":
      extra.y = -Math.abs(Math.sin(t * 3.0)) * 0.13;
      fly.rotation.z = Math.sin(t * 2.0) * 0.15;
      break;
    case "slow_pulse":
      squash = 1 + Math.sin(t * 1.1) * 0.05;
      break;
    case "lift_off":
      extra.y = Math.min(1, (t % 1.2) / 1.2) * 0.35;
      fly.rotation.x = -Math.min(1, (t % 1.2) / 1.2) * 0.25;
      break;
    case "fly_circle":
      extra.x = Math.cos(t * 1.5) * 0.4;
      extra.z = Math.sin(t * 3.0) * 0.12;
      extra.y = Math.sin(t * 2.2) * 0.16;
      if (fly.userData.billboard) {
        fly.rotation.z = Math.sin(t * 1.2) * 0.25;
      } else {
        fly.rotation.y += spec.speed * 0.06;
      }
      break;
    case "swoop": {
      const phase = (t % 1.2) / 1.2;
      extra.y = -Math.min(1, phase) * 0.35;
      fly.rotation.x = Math.min(1, phase) * 0.2;
      break;
    }
    case "circle":
      extra.x = Math.cos(t * 0.9) * 0.05;
      extra.z = Math.sin(t * 0.9) * 0.05;
      break;
    default:
      break;
  }
  fly.position.copy(runtime.pos).add(extra);
  fly.position.x = Math.min(3.6, Math.max(-3.6, fly.position.x));
  fly.position.y = Math.min(2.2, Math.max(-0.9, fly.position.y));
  fly.position.z = Math.min(2.0, Math.max(-2.4, fly.position.z));

  const spriteW = (fly.userData.billboard ? 0.14 : 0.1);
  const spriteH = (fly.userData.billboard ? 0.13 : 0.09);
  const ndc = new THREE.Vector3(fly.position.x, fly.position.y, fly.position.z).project(camera);
  const leftLimit = ((170 / window.innerWidth) * 2 - 1) + 0.06;
  const rightLimit = ((window.innerWidth - 320) / window.innerWidth) * 2 - 1 - spriteW;
  const topLimit = (1 - (90 / window.innerHeight) * 2) - spriteH;
  const px = THREE.MathUtils.clamp(ndc.x, leftLimit, rightLimit);
  const py = THREE.MathUtils.clamp(ndc.y, -0.86, topLimit);
  if (px !== ndc.x || py !== ndc.y) {
    const depth = Math.max(0.5, fly.position.distanceTo(camera.position));
    const perNdc = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * depth;
    fly.position.y += (py - ndc.y) * perNdc;
    fly.position.x += (px - ndc.x) * perNdc * camera.aspect;
  }

  fly.scale.set(baseScale * squash, baseScale * squash, baseScale);

  if (performance.now() >= runtime.until) {
    returnToIdle();
  }
  if (bubble.style.display !== "none") {
    positionBubble();
  }
  renderer.render(scene, camera);
}

let socket = null;
function connect() {
  try {
    socket = new WebSocket(WS_URL);
  } catch {
    setOffline(true);
    return;
  }
  socket.onopen = () => {
    wsDot.style.background = "#2ecc71";
    wsDot.title = "connected";
  };
  socket.onclose = () => {
    wsDot.style.background = "#e67e22";
    wsDot.title = "disconnected, retrying";
    setTimeout(connect, 3000);
  };
  socket.onerror = () => {
    setOffline(true);
    socket.close();
  };
  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "developer_event") {
        applyDeveloperEvent(msg);
      } else if (msg.type === "fly_behavior") {
        applyDecision({ ...msg.decision, behavior_id: msg.behavior_id });
        if (msg.context) showBubble(msg.context);
      }
    } catch {
      hudTag.textContent = "malformed ws payload";
    }
  };
}

function setOffline(offline) {
  runtime.offline = offline;
  wsDot.style.background = offline ? "#e74c3c" : "#2ecc71";
  wsDot.title = offline ? "backend unreachable -> local demo" : "connected";
  hudTag.textContent = offline
    ? "Backend unreachable. Use Demo cycle."
    : `WS ${WS_URL}`;
}

async function post(path, body) {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`http ${res.status}`);
    const data = await res.json();
    if (path === "/events") {
      applyDecision({ ...data, behavior_id: data.behaviorId });
    }
    return data;
  } catch {
    setOffline(true);
    if (path === "/events") {
      demoDecision(body);
    }
    return null;
  }
}

function demoDecision(body) {
  const map = {
    important_message: "IMPORTANT",
    warning: "WARNING",
    process_completed: "SUCCESS",
    process_failed: "ERROR",
    user_message: "LISTENING",
    task_reminder: "ATTENTION",
    calendar_event: "IMPORTANT",
    notification: "ATTENTION",
    app_open: "CURIOUS",
    app_idle: "IDLE",
  };
  let state = map[body.event] || (body.priority >= 0.7 ? "IMPORTANT" : "IDLE");
  const flightOn = document.getElementById("flight-mode")?.checked;
  if (flightOn && (state === "SUCCESS" || state === "CURIOUS") && (body.priority ?? 0.5) >= 0.3) {
    state = "FLYING";
  }
  applyDecision({ fetch: state, priorityLevel: "LOCAL", behavior_id: `local_${body.event}` });
  if (body.context && body.context.body_preview) showBubble(body.context);
}

function wireControls() {
  const templates = {
    "important_message": 0.9,
    "warning": 0.95,
    "process_completed": 0.7,
    "process_failed": 0.6,
    "user_message": 0.5,
    "task_reminder": 0.6,
    "calendar_event": 0.8,
    "notification": 0.4,
    "app_open": 0.3,
    "app_idle": 0.1,
  };
  const eventPicker = document.getElementById("event-picker");
  const priority = document.getElementById("priority");
  const priorityValue = document.getElementById("priority-value");
  const topic = document.getElementById("topic");
  const msg = document.getElementById("msg");
  const sendBtn = document.getElementById("send");
  priority.addEventListener("input", () => {
    priorityValue.textContent = parseFloat(priority.value).toFixed(2);
  });
  for (const name of Object.keys(templates)) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    eventPicker.appendChild(opt);
  }
  sendBtn.addEventListener("click", async () => {
    const context = { topic: topic.value.trim() || "general", urgency: "medium" };
    const message = msg.value.trim();
    if (message) {
      context.body_preview = message;
      context.sender_name = "Demo";
    }
    const result = await post("/events", {
      event: eventPicker.value,
      source: "demo",
      priority: parseFloat(priority.value),
      context,
    });
    if (result && result.fetch) {
      showToast(`Event <span class="t-k">sent</span> → Fly: <span class="t-r">${esc(result.fetch)}</span>`);
    }
    if (context.body_preview) showBubble(context);
  });
  document.getElementById("demo-cycle").addEventListener("click", () => {
    setOffline(true);
    const cycle = ["IMPORTANT", "THINKING", "SUCCESS", "CURIOUS", "IDLE"];
    let i = 0;
    applyDecision({ fetch: cycle[i], priorityLevel: "DEMO" });
    const interval = setInterval(() => {
      i += 1;
      if (i >= cycle.length) {
        clearInterval(interval);
        applyDecision({ fetch: "IDLE", priorityLevel: "DEMO" });
        return;
      }
      applyDecision({ fetch: cycle[i], priorityLevel: "DEMO" });
    }, 2600);
  });
  const feedbackBtns = document.querySelectorAll("[data-feedback]");
  for (const btn of feedbackBtns) {
    btn.addEventListener("click", async () => {
      const feedback = btn.dataset.feedback;
      const result = await post("/feedback", { behaviorId: runtime.behaviorId || "behavior_demo", feedback });
      if (result && typeof result === "object" && "reward_value" in result) {
        const n = result.synapse_delta ? Object.keys(result.synapse_delta).length : 0;
        const sign = result.reward_value > 0 ? "+" : result.reward_value < 0 ? "" : "±";
        showToast(
          `Feedback <span class="t-k">${esc(feedback)}</span> · reward <span class="t-r">${sign}${esc(result.reward_value)}</span> · ${n} synapses updated`,
        );
      } else if (result) {
        showToast(`Feedback <span class="t-k">${esc(feedback)}</span> · accepted`);
      } else {
        showToast(`Feedback <span class="t-k">${esc(feedback)}</span> · offline — could not reach the brain`);
      }
    });
  }
  const devMode = document.getElementById("dev-mode");
  const syncDevMode = async () => {
    try {
      const res = await fetch(`${API_URL}/developer/mode`);
      if (!res.ok) throw new Error(`http ${res.status}`);
      const data = await res.json();
      devMode.checked = !!data.enabled;
    } catch {
      setOffline(true);
    }
  };
  devMode.addEventListener("change", () => {
    post("/developer/mode", { enabled: devMode.checked });
  });
  syncDevMode();

  const flightMode = document.getElementById("flight-mode");
  const syncFlight = async () => {
    try {
      const res = await fetch(`${API_URL}/mode/flight`);
      if (!res.ok) throw new Error(`http ${res.status}`);
      const data = await res.json();
      flightMode.checked = !!data.flight;
    } catch {
      setOffline(true);
    }
  };
  flightMode.addEventListener("change", async () => {
    const result = await post("/mode/flight", { flight: flightMode.checked });
    if (result && "flight" in result) {
      showToast(
        `Flight mode <span class="t-k">${result.flight ? "ON" : "OFF"}</span> — fly ${
          result.flight ? "can take off (free flight)" : "perches, only reacts to events"
        }`,
      );
    }
  });
  syncFlight();
}

wireControls();
connect();
setOffline(false);
tickLoop();

const unlockAudioOnce = () => {
  unlockAudio();
  window.removeEventListener("pointerdown", unlockAudioOnce);
  window.removeEventListener("keydown", unlockAudioOnce);
};
window.addEventListener("pointerdown", unlockAudioOnce);
window.addEventListener("keydown", unlockAudioOnce);

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});