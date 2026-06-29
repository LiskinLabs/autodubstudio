import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: [
    "@storybook/addon-a11y",
    "@storybook/addon-links",
  ],
  framework: "@storybook/react-vite",
  core: {
    disableTelemetry: true,
  },
  docs: {
    autodocs: "tag",
  },
};

export default config;
