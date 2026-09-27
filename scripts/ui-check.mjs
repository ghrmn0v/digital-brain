#!/usr/bin/env node
/**
 * Browser-level UI checks.
 *
 * The Vitest suite runs in a node environment with no jsdom, so nothing in it
 * can see whether a page actually renders, whether a client fetch fails, or
 * whether a drawer holds focus. Those are the failures that matter most in a
 * UI, and they are the ones a type checker will never report. This drives a real
 * Chrome over the DevTools Protocol instead, using Node's built-in WebSocket, so
 * it needs no new dependency.
 *
 * Two checks:
 *   1. Every route loads, renders real content, and produces no console error,
 *      uncaught exception or failed request while idle.
 *   2. Each mobile drawer pulls focus in, keeps it inside across Tab and
 *      Shift+Tab, closes on Escape, returns focus to its toggle and releases the
 *      body scroll lock.
 *
 * Prerequisites: Product on http://127.0.0.1:3000 and a Chrome listening on
 * 9222. Start Chrome with:
 *   google-chrome --headless --disable-gpu --no-sandbox --remote-debugging-port=9222
 *
 * Exits non-zero if anything fails, so it is usable as a gate.
 */

const CDP = process.env.CDP_URL ?? "http://127.0.0.1:9222";
const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const MOBILE = { width: 390, height: 844, deviceScaleFactor: 1, mobile: true };
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false };

/*
 * Every page the app actually has.
 *
 * This list was written before the product-UI merge and had drifted: it covered
 * 17 routes while the app served 18, and the two it missed were /brain — a
 * primary page — and /connections. A harness that does not know about a route
 * cannot tell you that route broke. Kept in step with the page.tsx files under src/app.
 */
const ROUTES = [
  "/", "/dashboard", "/connectome", "/chat", "/brain", "/permissions",
  "/connections", "/settings", "/timeline", "/tasks", "/calendar", "/jobs",
  "/approvals", "/automations", "/connectors", "/developer",
  "/developer-information", "/memory", "/people",
];

const DRAWERS = [
  { route: "/dashboard", id: "mobile-navigation", toggle: "Open navigation" },
  { route: "/connectome", id: "connectome-navigation", toggle: "Open context navigation" },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connect() {
  let res;
  try {
    res = await fetch(`${CDP}/json/new?about:blank`, { method: "PUT" });
  } catch (cause) {
    throw new Error(
      `No Chrome on ${CDP}. Start one with: google-chrome --headless ` +
        `--disable-gpu --no-sandbox --remote-debugging-port=9222`,
    );
  }
  const target = await res.json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));

  let id = 0;
  const pending = new Map();
  const listeners = new Set();
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      return;
    }
    for (const fn of listeners) fn(msg);
  };

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const n = ++id;
      pending.set(n, { resolve, reject });
      ws.send(JSON.stringify({ id: n, method, params }));
    });

  const on = (fn) => {
    listeners.add(fn);
    return () => listeners.delete(fn);
  };

  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  };

  return { ws, send, on, evaluate };
}

async function navigate(cdp, url) {
  let loaded = false;
  const off = cdp.on((m) => {
    if (m.method === "Page.loadEventFired") loaded = true;
  });
  await cdp.send("Page.navigate", { url });
  for (let i = 0; i < 100 && !loaded; i++) await sleep(100);
  off();
  // Let the page's own fetches finish before anything is judged. Requests still
  // in flight when the next navigation starts are aborted by that navigation and
  // would otherwise be blamed on the following page.
  await sleep(1500);
}

async function checkRoutes(cdp, failures) {
  console.log(`\n== routes (${ROUTES.length}) ==`);
  let bucket = { console: [], exceptions: [], failed: [] };

  const offConsole = cdp.on((m) => {
    if (m.method === "Runtime.consoleAPICalled") {
      const type = m.params.type;
      if (type !== "error" && type !== "warning") return;
      const text = (m.params.args ?? [])
        .map((a) => a.value ?? a.description ?? a.unserializableValue ?? "")
        .join(" ");
      bucket.console.push(`[${type}] ${text}`.slice(0, 300));
    }
  });
  const offException = cdp.on((m) => {
    if (m.method !== "Runtime.exceptionThrown") return;
    const d = m.params.exceptionDetails;
    bucket.exceptions.push((d.exception?.description ?? d.text ?? "").slice(0, 300));
  });
  const offFailed = cdp.on((m) => {
    if (m.method !== "Network.loadingFailed") return;
    const { type, errorText, blockedReason } = m.params;
    bucket.failed.push(`${type} ${errorText} ${blockedReason ?? ""}`.trim());
  });

  for (const route of ROUTES) {
    await navigate(cdp, BASE + route);
    // Recorded only once the page is idle, so navigation aborts are excluded.
    bucket = { console: [], exceptions: [], failed: [] };
    await sleep(1200);

    const rendered = JSON.parse(
      await cdp.evaluate(`JSON.stringify({
        h1: (document.querySelector('h1')?.textContent ?? document.title ?? '').trim().slice(0, 60),
        // Fall back to the body when a layout has no <main>. The full-screen
        // chat shell is one, and measuring <main> alone reported a page that
        // was rendering perfectly as "0 characters" — a false failure caused
        // by the checker's assumption rather than by the page.
        chars: (document.querySelector('main')?.innerText ?? document.body.innerText ?? '').trim().length,
      })`),
    );
    const issues = [
      ...bucket.console,
      ...bucket.exceptions,
      ...bucket.failed,
    ];
    if (rendered.chars < 40) issues.push(`rendered only ${rendered.chars} chars`);
    if (issues.length) {
      failures.push(`${route}: ${issues.join(" | ")}`);
      console.log(`  FAIL ${route}  h1="${rendered.h1}" chars=${rendered.chars}`);
      for (const i of issues) console.log(`       ${i}`);
    } else {
      console.log(`  ok   ${route}  h1="${rendered.h1}" chars=${rendered.chars}`);
    }
  }

  offConsole();
  offException();
  offFailed();
}

async function checkDrawers(cdp, failures) {
  console.log(`\n== mobile drawers (${DRAWERS.length}) ==`);
  await cdp.send("Emulation.setDeviceMetricsOverride", DESKTOP);

  const describe = (id) => `(() => {
    const a = document.activeElement;
    const drawer = document.querySelector('#${id}');
    return {
      label: a ? (a.getAttribute('aria-label') || a.textContent || '').trim().slice(0, 30) : null,
      inside: drawer ? drawer.contains(a) : null,
    };
  })()`;

  const press = async (key, code, vk, modifiers = 0) => {
    for (const type of ["rawKeyDown", "keyUp"]) {
      await cdp.send("Input.dispatchKeyEvent", {
        type, key, code, modifiers,
        windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk,
      });
    }
    await sleep(60);
  };

  for (const { route, id, toggle } of DRAWERS) {
    const problems = [];
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
      source: `window.__DRAWER_ID = ${JSON.stringify(id)}`,
    });
    await cdp.send("Emulation.setDeviceMetricsOverride", MOBILE);
    await navigate(cdp, BASE + route);

    const opened = await cdp.evaluate(`(() => {
      const btn = [...document.querySelectorAll('button')]
        .find((b) => b.getAttribute('aria-label') === ${JSON.stringify(toggle)});
      if (!btn) return 'no toggle';
      btn.click();
      return 'clicked';
    })()`);
    if (opened !== "clicked") {
      problems.push(`could not open: ${opened}`);
    } else {
      await sleep(400);
      const state = await cdp.evaluate(describe(id));
      if (state.inside !== true) {
        problems.push(`focus not moved into drawer (on ${state.label})`);
      }
      const count = await cdp.evaluate(
        `document.querySelectorAll('#${id} a[href], #${id} button:not([disabled])').length`,
      );
      if (count === 0) problems.push("drawer has no focusable children");

      // One full cycle forwards and a few backwards, then check Escape.
      for (let i = 0; i < count + 2; i++) {
        await press("Tab", "Tab", 9);
        const s = await cdp.evaluate(describe(id));
        if (s.inside === false) { problems.push(`focus escaped on Tab #${i + 1}`); break; }
      }
      for (let i = 0; i < 3; i++) {
        await press("Tab", "Tab", 9, 8);
        const s = await cdp.evaluate(describe(id));
        if (s.inside === false) { problems.push(`focus escaped on Shift+Tab #${i + 1}`); break; }
      }
      await press("Escape", "Escape", 27);
      await sleep(400);
      const after = JSON.parse(
        await cdp.evaluate(`JSON.stringify({
          closed: !document.querySelector('#${id}'),
          focus: (document.activeElement?.getAttribute('aria-label') ?? '').trim(),
          scrollLocked: document.body.style.overflow !== '',
        })`),
      );
      if (!after.closed) problems.push("Escape did not close the drawer");
      if (after.scrollLocked) problems.push("body scroll left locked after close");
      if (after.focus !== toggle) {
        problems.push(`focus after close is "${after.focus}", expected "${toggle}"`);
      }
    }

    if (problems.length) {
      failures.push(`${route} drawer: ${problems.join(" | ")}`);
      console.log(`  FAIL ${route}  ${problems.join(" | ")}`);
    } else {
      console.log(`  ok   ${route}  trap holds, Escape closes, focus returns`);
    }
  }
  await cdp.send("Emulation.setDeviceMetricsOverride", DESKTOP);
}

const cdp = await connect();
const failures = [];
try {
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Network.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", DESKTOP);
  await checkRoutes(cdp, failures);
  await checkDrawers(cdp, failures);
} finally {
  cdp.ws.close();
}

console.log(
  failures.length
    ? `\nFAILED (${failures.length}):\n${failures.map((f) => `  - ${f}`).join("\n")}`
    : "\nAll UI checks passed.",
);
process.exit(failures.length ? 1 : 0);
