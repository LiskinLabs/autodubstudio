import type { Preview } from "@storybook/react";
import { FluentProvider, webDarkTheme, webLightTheme } from "@fluentui/react-components";
import React from "react";
import "../src/index.css";

/** All supported themes for AutoDubStudio */
const THEMES = {
  "🌙 Dark (Win11)": webDarkTheme,
  "☀️ Light (Win11)": webLightTheme,
} as const;

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      // WCAG 2.1 AA — как в DESIGN.md
      config: {
        rules: [
          { id: "color-contrast", enabled: true },
        ],
      },
    },
    backgrounds: {
      disable: true, // FluentProvider управляет фоном
    },
    layout: "fullscreen",
  },

  decorators: [
    (Story, context) => {
      const themeKey = (context.globals.theme as keyof typeof THEMES) ?? "🌙 Dark (Win11)";
      const theme = THEMES[themeKey] ?? webDarkTheme;

      return (
        <FluentProvider theme={theme} style={{ height: "100%", minHeight: "100vh" }}>
          <Story />
        </FluentProvider>
      );
    },
  ],

  globalTypes: {
    theme: {
      name: "Theme",
      description: "Windows 11 theme",
      defaultValue: "🌙 Dark (Win11)",
      toolbar: {
        icon: "paintbrush",
        items: Object.keys(THEMES).map((key) => ({
          value: key,
          title: key,
        })),
        dynamicTitle: true,
      },
    },
  },

  tags: ["autodocs"],
};

export default preview;
