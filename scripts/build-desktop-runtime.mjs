#!/usr/bin/env node
/**
 * Assemble the runtime the desktop app ships with.
 *
 * The Electron window loads `http://localhost:3000`, so the app is not a shell
 * around something the person already has running — it has to bring its own
 * Product and Brain, or the window opens onto nothing. This builds that payload
 * into `desktop/runtime/`, which electron-builder copies verbatim into the
 * installed app via `extraResources`.
 *
 * What goes in:
 *   product/  the Next standalone server, its static assets, public/, and prisma/
 *             so the schema can be applied on first run
 *   brain/    the Core Brain sources plus the virtualenv it runs on
 *   fly/      the Fly connectome sources (its Spring half is a separate build)
 *
 * What deliberately stays out, because shipping it would be worse than not
 * shipping it: every `*.db` (including the checkout's own test.db and
 * integration.db), `data/`, `logs/`, `docs/`, `tests/`, `.demo/`, and any `.env`
 * or key file. An installer is a thing that leaves the machine; a developer's
 * memories and an API key must not ride along inside it.
 *
 * Usage:  node scripts/build-desktop-runtime.mjs [--skip-next-build]
 */

import { cp, mkdir, rm, stat, readdir, access, readFile } from "node:fs/promises";
import { constants } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..");
const runtime = path.join(repo, "desktop", "runtime");
const standalone = path.join(repo, ".next", "standalone");

/** The venv the Brain runs on. Lives beside the repo during development. */
const BRAIN_VENV = process.env.CEREBRO_BRAIN_VENV
  ?? "/home/user/AllProjects/digital-brain/.venv";

/** Never copied, wherever they appear. */
const FORBIDDEN = new Set([
  ".env",
  ".env.local",
  ".env.production",
  "test.db",
  "integration.db",
  "ci.db",
]);

const skipNextBuild = process.argv.includes("--skip-next-build");

/** @param {string} p */
async function exists(p) {
  try {
    await access(p, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

/** @param {string} p */
async function dirSize(p) {
  const out = spawnSync("du", ["-sh", p], { encoding: "utf8" });
  return (out.stdout || "").trim().split(/\s+/)[0] ?? "?";
}

/**
 * Copy a tree, refusing anything that looks like state rather than code.
 *
 * The refusal is a guard, not a filter: a `*.db` reachable from a directory we
 * thought was source is a bug in this script, and quietly skipping it would hide
 * that bug until someone opened the installed app and found the developer's
 * memories in it.
 */
async function copyTree(from, to, { label }) {
  if (!(await exists(from))) {
    throw new Error(`${label}: missing source ${from}`);
  }
  await cp(from, to, {
    recursive: true,
    filter: (src) => {
      const base = path.basename(src);
      if (FORBIDDEN.has(base)) {
        throw new Error(
          `${label}: refusing to package ${base} from ${path.relative(repo, src)} — ` +
            "an installer must not carry a database or a key",
        );
      }
      if (base.endsWith(".db") || base.endsWith(".db-wal") || base.endsWith(".db-shm")) {
        throw new Error(
          `${label}: refusing to package ${base} from ${path.relative(repo, src)}`,
        );
      }
      return true;
    },
  });
  return dirSize(to);
}

async function main() {
  const steps = [];

  if (!skipNextBuild) {
    process.stdout.write("  building Product (next build, standalone)...\n");
    const build = spawnSync("npm", ["run", "build"], { cwd: repo, stdio: "inherit" });
    if (build.status !== 0) throw new Error("next build failed");
  }

  if (!(await exists(path.join(standalone, "server.js")))) {
    throw new Error(
      "no standalone build found at .next/standalone — run `npm run build` first",
    );
  }

  process.stdout.write("  clearing previous runtime...\n");
  await rm(runtime, { recursive: true, force: true });
  await mkdir(runtime, { recursive: true });

  // -- product ---------------------------------------------------------------
  // The traced standalone tree also contains the whole repository (its Python
  // packages, docs, and the checkout's own databases), because the app and its
  // sources share a root. Copying it wholesale would ship all of that, so the
  // runtime is assembled from the parts the server actually needs at runtime.
  const product = path.join(runtime, "product");
  await mkdir(product, { recursive: true });
  process.stdout.write("  copying Product server...\n");
  steps.push(["product/server", await copyTree(path.join(standalone, "server.js"), path.join(product, "server.js"), { label: "product" })]);
  steps.push([
    "product/node_modules",
    await copyTree(path.join(standalone, "node_modules"), path.join(product, "node_modules"), { label: "product" }),
  ]);
  steps.push([
    "product/.next",
    await copyTree(path.join(standalone, ".next"), path.join(product, ".next"), { label: "product" }),
  ]);
  // Next deliberately leaves the static assets out of the standalone tree: they
  // are not imported by the server, so tracing never sees them. Without this the
  // server starts and then serves a page with no CSS, no JS and no icons, which
  // looks like a broken install rather than a missing directory.
  steps.push([
    "product/.next/static",
    await copyTree(path.join(repo, ".next", "static"), path.join(product, ".next", "static"), { label: "product" }),
  ]);
  steps.push(["product/public", await copyTree(path.join(repo, "public"), path.join(product, "public"), { label: "product" })]);
  // prisma/ is not imported by the running app, so file tracing drops it. The
  // migrations are still needed: a fresh install has a database file with no
  // tables in it until `migrate deploy` has run.
  steps.push(["product/prisma", await copyTree(path.join(repo, "prisma"), path.join(product, "prisma"), { label: "product" })]);
  // Prisma 7 reads the datasource URL from prisma.config.ts, and `migrate
  // deploy` refuses to run without one — so a runtime without this file has a
  // database it can never give a schema to.
  steps.push([
    "product/prisma.config.ts",
    await copyTree(path.join(repo, "prisma.config.ts"), path.join(product, "prisma.config.ts"), { label: "product" }),
  ]);
  steps.push([
    "product/package.json",
    await copyTree(path.join(repo, "package.json"), path.join(product, "package.json"), { label: "product" }),
  ]);
  // The generated Prisma client lives in src/ and is reached through the traced
  // tree; copy it explicitly so the client never depends on tracing behaviour.
  const generated = path.join(repo, "src", "generated", "prisma");
  if (await exists(generated)) {
    steps.push([
      "product/src/generated/prisma",
      await copyTree(generated, path.join(product, "src", "generated", "prisma"), { label: "product" }),
    ]);
  }

  // The Prisma CLI is invoked, never imported, so file tracing has no reason to
  // include it and does not. Without it a freshly installed app has a database
  // file with no tables in it and no way to create them. Copied by hand, and the
  // packages the traced tree already carries are left alone.
  process.stdout.write("  copying Prisma CLI (not traced by Next)...\n");
  const targetModules = path.join(product, "node_modules");
  const cli = path.join(repo, "node_modules", "prisma");
  if (await exists(cli)) {
    steps.push([
      "product/node_modules/prisma",
      await copyTree(cli, path.join(targetModules, "prisma"), { label: "product" }),
    ]);
  } else {
    throw new Error("product: node_modules/prisma is missing; run `npm install` first");
  }
  const prismaScope = path.join(repo, "node_modules", "@prisma");
  // studio-core (43M) and dev (19M) are a GUI and a dev toolbox. Neither is
  // reachable from `migrate deploy`, and an installer is not the place to carry
  // them.
  const NOT_NEEDED = new Set(["studio-core", "dev", "studio"]);
  const roots = ["prisma"];
  if (await exists(prismaScope)) {
    for (const entry of await readdir(prismaScope)) {
      if (NOT_NEEDED.has(entry)) continue;
      roots.push(`@prisma/${entry}`);
    }
  }

  // The CLI has transitive dependencies the traced tree never saw, because
  // nothing the server runs imports them. `effect`, pulled in by @prisma/config,
  // is one: without it the migration dies on a module resolution error before it
  // reads a single migration. Walking the real dependency graph is the only way
  // to get all of them, rather than discovering them one crash at a time.
  const queue = [...roots];
  const seen = new Set(roots);
  const missing = [];
  while (queue.length) {
    const name = queue.shift();
    const dest = path.join(targetModules, name);
    if (await exists(dest)) continue; // already present, traced or copied
    missing.push(name);
    const manifest = path.join(repo, "node_modules", name, "package.json");
    if (!(await exists(manifest))) continue;
    const pkg = JSON.parse(await readFile(manifest, "utf8"));
    for (const dep of Object.keys(pkg.dependencies ?? {})) {
      if (seen.has(dep)) continue;
      // Optional peers that are not installed must not stop the walk.
      if (!(await exists(path.join(repo, "node_modules", dep)))) continue;
      seen.add(dep);
      queue.push(dep);
    }
  }
  for (const name of missing) {
    steps.push([
      `product/node_modules/${name}`,
      await copyTree(path.join(repo, "node_modules", name), path.join(targetModules, name), { label: "product" }),
    ]);
  }

  // -- brain -----------------------------------------------------------------
  const brain = path.join(runtime, "brain");
  await mkdir(brain, { recursive: true });
  process.stdout.write("  copying Core Brain sources...\n");
  for (const dir of ["core", "contracts"]) {
    steps.push([
      `brain/${dir}`,
      await copyTree(path.join(repo, dir), path.join(brain, dir), { label: "brain" }),
    ]);
  }
  if (!(await exists(BRAIN_VENV))) {
    throw new Error(
      `brain: no virtualenv at ${BRAIN_VENV}. Create one, or point ` +
        "CEREBRO_BRAIN_VENV at it. The Brain needs pydantic, websockets and " +
        "python-dotenv.",
    );
  }
  process.stdout.write("  copying Brain virtualenv...\n");
  steps.push(["brain/.venv", await copyTree(BRAIN_VENV, path.join(brain, ".venv"), { label: "brain" })]);

  // -- fly -------------------------------------------------------------------
  const fly = path.join(runtime, "fly");
  await mkdir(fly, { recursive: true });
  process.stdout.write("  copying Fly connectome...\n");
  steps.push([
    "fly/connectome",
    await copyTree(path.join(repo, "connectome", "connectome"), path.join(fly, "connectome"), { label: "fly" }),
  ]);

  // -- report ----------------------------------------------------------------
  process.stdout.write("\n  runtime assembled at desktop/runtime\n");
  for (const [name, size] of steps) {
    process.stdout.write(`    ${name.padEnd(30)} ${size}\n`);
  }
  const entries = await readdir(runtime);
  process.stdout.write(`  parts: ${entries.join(", ")}\n`);

  const pyvenv = path.join(runtime, "brain", ".venv", "pyvenv.cfg");
  if (await exists(pyvenv)) {
    process.stdout.write(
      "\n  note: the bundled virtualenv links to the Python it was built with " +
        "(see pyvenv.cfg).\n" +
        "        An installed copy needs that same interpreter present at the " +
        "same path.\n",
    );
  }
  await stat(runtime);
}

main().catch((error) => {
  process.stderr.write(`\n  build-desktop-runtime failed: ${error.message}\n`);
  process.exitCode = 1;
});
