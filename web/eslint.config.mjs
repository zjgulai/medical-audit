import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitalsConfig from "eslint-config-next/core-web-vitals.js";
import nextTypescriptConfig from "eslint-config-next/typescript.js";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname
});

const eslintConfig = defineConfig([
  ...compat.config(nextVitalsConfig),
  ...compat.config(nextTypescriptConfig),
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "coverage/**",
    "next-env.d.ts",
    "test-results/**",
    "playwright-report/**"
  ])
]);

export default eslintConfig;
