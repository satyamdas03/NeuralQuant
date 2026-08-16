import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // This rule (new in eslint-plugin-react-hooks v6) flags the idiomatic
      // "setLoading(true) → fetch → setLoading(false)" data-fetching pattern and
      // "reset state when a prop changes" effects. Both are correct here; the
      // rule targets unnecessary synchronous setState, which this codebase does
      // not do. Disabled to avoid false positives on legitimate patterns.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
