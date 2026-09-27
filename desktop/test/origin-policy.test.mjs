import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_TARGET,
  TargetError,
  isAllowedUrl,
  resolveMode,
  resolveTarget,
  safeOrigin,
} from "../src/origin-policy.mjs";

/**
 * The desktop shell loads a web server, so the load-bearing question is no
 * longer "is this remote" but "can this be made to leave the machine". These
 * tests are the enforcement point for that, which is why the policy is a module
 * rather than a few lines inside main.js.
 */

test("the default target is the local web interface", () => {
  assert.equal(DEFAULT_TARGET, "http://localhost:3000");
  assert.deepEqual(resolveTarget(undefined), {
    url: "http://localhost:3000/",
    origin: "http://localhost:3000",
  });
});

test("a blank or whitespace target falls back to the default", () => {
  for (const value of ["", "   ", null, undefined]) {
    assert.equal(resolveTarget(value).origin, "http://localhost:3000");
  }
});

test("every loopback host is accepted, each keeping its own origin", () => {
  // Origins are compared exactly, so 127.0.0.1 and localhost are deliberately
  // *not* interchangeable: if the shell is pointed at one, a link to the other
  // is a different origin and is refused rather than quietly allowed.
  for (const [value, origin] of [
    ["http://localhost:3000", "http://localhost:3000"],
    ["http://127.0.0.1:3000", "http://127.0.0.1:3000"],
    ["http://[::1]:3000", "http://[::1]:3000"],
    ["http://localhost:3000/", "http://localhost:3000"],
    ["http://localhost:3000/dashboard", "http://localhost:3000"],
  ]) {
    assert.equal(resolveTarget(value).origin, origin, value);
  }
});

test("a port that is not allowed is refused", () => {
  assert.throws(() => resolveTarget("http://localhost:8080"), TargetError);
  assert.throws(() => resolveTarget("http://127.0.0.1:9999"), TargetError);
});

test("an explicitly allowed extra port is honoured", () => {
  assert.equal(
    resolveTarget("http://localhost:8080", [3000, 8080]).origin,
    "http://localhost:8080",
  );
});

test("remote hosts are refused, including ones that resolve to loopback", () => {
  // The important one is last: a hostname that resolves to 127.0.0.1 is still
  // refused, because the answer can change between this check and the request.
  for (const value of [
    "http://example.com:3000",
    "http://evil.test:3000",
    "http://127.0.0.1.evil.test:3000",
    "http://localhost.evil.test:3000",
    "http://0.0.0.0:3000",
    "http://192.168.0.175:3000",
  ]) {
    assert.throws(() => resolveTarget(value), TargetError, value);
  }
});

test("non-http schemes are refused", () => {
  for (const value of [
    "https://localhost:3000",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "data:text/html,<h1>x</h1>",
    "ftp://localhost:3000",
  ]) {
    assert.throws(() => resolveTarget(value), TargetError, value);
  }
});

test("a non-URL target is refused rather than guessed at", () => {
  for (const value of ["not a url", "localhost:3000", "//localhost:3000", "://"]) {
    assert.throws(() => resolveTarget(value), TargetError, value);
  }
});

test("an IPv6 loopback literal is matched with or without brackets", () => {
  assert.equal(resolveTarget("http://[::1]:3000").origin, "http://[::1]:3000");
});

test("navigation is allowed anywhere inside the same origin", () => {
  const origin = "http://localhost:3000";
  for (const path of [
    "http://localhost:3000/",
    "http://localhost:3000/dashboard",
    "http://localhost:3000/connectome?node=abc",
    "http://localhost:3000/chat#grounded",
  ]) {
    assert.equal(isAllowedUrl(path, origin), true, path);
  }
});

test("navigation off the origin is refused, including lookalikes", () => {
  const origin = "http://localhost:3000";
  for (const value of [
    "http://localhost:3001/",
    "http://127.0.0.1:3000/",
    "https://localhost:3000/",
    "http://evil.test:3000/",
    "http://localhost:3000.evil.test/",
    "file:///etc/passwd",
    "about:blank",
    "not a url",
  ]) {
    assert.equal(isAllowedUrl(value, origin), false, value);
  }
});

test("a bad configured target degrades to the default instead of crashing", () => {
  // The shell must still open. A misconfigured env var should show the app at
  // the known-good address, not a stack trace and no window.
  for (const value of ["https://example.com", "nonsense", "http://localhost:9999"]) {
    assert.equal(safeOrigin(value, [3000]), "http://localhost:3000", value);
  }
});

test("a good configured target is used as given", () => {
  assert.equal(safeOrigin("http://127.0.0.1:3000", [3000]), "http://127.0.0.1:3000");
});

test("the mode defaults to the web app and rejects nonsense", () => {
  assert.equal(resolveMode(undefined), "web");
  assert.equal(resolveMode(""), "web");
  assert.equal(resolveMode("  WEB "), "web");
  assert.equal(resolveMode("fly"), "fly");
  assert.equal(resolveMode("evil"), "web");
});
