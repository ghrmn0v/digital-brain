import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "coverage/**",
    "src/generated/**",
    "next-env.d.ts",
    // Other owners' subsystems share this repository but not this lint config.
    // They keep their own conventions (Fly's Electron and gateway code is
    // CommonJS by design), so linting them with the Product rules would report
    // another owner's style as an error. Each has its own checks: the Core
    // Brain client runs `tsc`, Fly runs unittest and `node --test`.
    "core/**",
    "contracts/**",
    "clients/**",
    "backend/**",
    "connectome/**",
    "desktop/**",
    "whatsapp-gateway/**",
    "docs/**",
    "tests/**",
    "scripts/**",
  ]),
]);

export default eslintConfig;
