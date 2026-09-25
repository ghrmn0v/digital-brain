/**
 * Contract-drift and architecture-boundary tests for the TypeScript client.
 *
 * These are the guards that keep the client honest without a TypeScript
 * compiler: the runtime method table, error codes and definition names are
 * compared against the checked-in canonical schema artifact, and `src/` is
 * checked to stay free of Node-only and third-party imports so the same code
 * runs in a browser, a React Native app and Node.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { API_ERROR_CODES, API_METHODS, apiMethodSpecs } from "../src/index.ts";

const REPO_ROOT = join(import.meta.dirname, "..", "..", "..");
const SCHEMA_PATH = join(REPO_ROOT, "contracts", "schemas", "brain-api.v1.json");
const SRC_DIR = join(import.meta.dirname, "..", "src");

interface MethodEntry {
  readonly method: string;
  readonly params: string;
  readonly result: string;
}

interface SchemaFile {
  readonly "x-brain-api-version": string;
  readonly "x-methods": readonly MethodEntry[];
  readonly "x-contracts": Readonly<Record<string, string>>;
  readonly $defs: Readonly<Record<string, { readonly enum?: readonly string[] }>>;
}

const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf8")) as SchemaFile;

test("client method table matches the canonical schema in order", () => {
  const fromSchema = schema["x-methods"].map((entry) => entry.method);
  const fromClient = API_METHODS.map((entry) => entry.method);
  assert.deepEqual(fromClient, fromSchema);
  // Derived, not remembered: appending a method must not leave a stale literal
  // behind, while still failing if the client and the schema ever disagree.
  assert.equal(fromClient.length, fromSchema.length);
  assert.ok(fromClient.includes("search"));
  assert.ok(fromClient.includes("chat"));
});

test("client params/result definition names match the canonical schema", () => {
  const expected = schema["x-methods"].map((entry) => ({
    method: entry.method,
    paramsDef: entry.params.split("/").pop(),
    resultDef: entry.result.split("/").pop(),
  }));
  assert.deepEqual([...apiMethodSpecs()], expected);
});

test("client error codes match the canonical schema enum", () => {
  const fromSchema = schema.$defs["ApiErrorCode"]?.enum ?? [];
  assert.deepEqual([...API_ERROR_CODES], [...fromSchema]);
});

test("every method definition referenced by the client exists in the schema", () => {
  for (const spec of apiMethodSpecs()) {
    assert.ok(spec.paramsDef in schema.$defs, `missing params def ${spec.paramsDef}`);
    assert.ok(spec.resultDef in schema.$defs, `missing result def ${spec.resultDef}`);
  }
});

test("schema version is the version the client speaks", () => {
  assert.equal(schema["x-brain-api-version"], "v1");
  for (const contract of ["ApiRequest", "ApiResponse", "ApiError", "BrainEvent", "ResponseEnvelope", "EventEnvelope"]) {
    assert.ok(contract in schema["x-contracts"], `missing contract ${contract}`);
  }
});

test("client source has no Node-only or third-party imports", () => {
  const files = readdirSync(SRC_DIR).filter((name) => name.endsWith(".ts"));
  assert.ok(files.length >= 5, "expected the client sources to be present");
  for (const name of files) {
    const source = readFileSync(join(SRC_DIR, name), "utf8");
    const specifiers = [...source.matchAll(/from\s+"([^"]+)"/g)].map((match) => match[1] ?? "");
    for (const specifier of specifiers) {
      assert.ok(
        specifier.startsWith("./"),
        `${name} imports non-relative module "${specifier}"`,
      );
      assert.ok(
        !specifier.startsWith("node:"),
        `${name} imports Node builtin "${specifier}"`,
      );
      assert.ok(
        specifier.endsWith(".ts"),
        `${name} must import with an explicit .ts extension (got "${specifier}")`,
      );
    }
    assert.ok(!/\brequire\(/.test(source), `${name} uses require()`);
    assert.ok(!/\bdynamic import\b|\bimport\(/.test(source), `${name} uses a dynamic import`);
    assert.ok(!/\bprocess\./.test(source), `${name} touches the Node process global`);
    assert.ok(!/\bBuffer\b/.test(source), `${name} touches the Node Buffer global`);
  }
});
