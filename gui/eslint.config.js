import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import storybook from "eslint-plugin-storybook";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...storybook.configs["flat/recommended"],

  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      // React hooks
      ...reactHooks.configs.recommended.rules,

      // ❌ NO inline styles / div-onClick / hardcoded colors
      "no-restricted-syntax": [
        "warn",
        {
          selector: "JSXAttribute[name.name='style'][value.expression.type='ObjectExpression']",
          message: "Inline style={{}} detected! Use makeStyles() + Fluent tokens instead.",
        },
        {
          selector: "JSXElement[openingElement.name.name='div'] JSXAttribute[name.name='onClick']",
          message: "<div onClick> detected! Use Fluent UI <Button> instead.",
        },
        {
          selector: "Literal[value=/^#[0-9a-fA-F]{3,8}$/]",
          message: "Hardcoded color! Use Fluent color tokens (e.g. tokens.colorBrandForeground1).",
        },
      ],

      // General
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },

  {
    ignores: [
      "node_modules/",
      "dist/",
      "src-tauri/",
      ".storybook/",
      "*.config.*",
    ],
  }
);
