import { execFileSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";

export default function setup() {
  const root = process.cwd();
  const databasePath = path.join(root, "test.db");

  if (existsSync(databasePath)) {
    rmSync(databasePath, { force: true });
  }

  execFileSync(
    process.execPath,
    ["node_modules/prisma/build/index.js", "migrate", "deploy"],
    {
      cwd: root,
      env: { ...process.env, DATABASE_URL: "file:./test.db" },
      stdio: "pipe",
    },
  );
}
