/**
 * AutoDubStudio — Windows 11 Native Themes
 * Pure Fluent UI v9: webLightTheme, webDarkTheme, teamsDarkTheme
 */
import {
  webLightTheme, webDarkTheme, teamsDarkTheme,
  type Theme,
} from "@fluentui/react-components";

export interface FluentThemeEntry {
  labelKey: string;
  theme: Theme;
}

/** Only real Fluent UI themes — mapped directly to Windows 11 looks */
export const FLUENT_THEMES: Record<string, FluentThemeEntry> = {
  light: { labelKey: "theme.light", theme: webLightTheme },
  dark:  { labelKey: "theme.dark",  theme: webDarkTheme },
  dim:   { labelKey: "theme.dim",   theme: teamsDarkTheme },
};

export function isThemeDark(key: string): boolean {
  return key === "dark" || key === "dim";
}

export function getFluentTheme(key: string): Theme {
  return FLUENT_THEMES[key]?.theme ?? webDarkTheme;
}

export const THEME_OPTIONS = Object.entries(FLUENT_THEMES).map(([k, v]) => ({
  value: k, labelKey: v.labelKey,
}));

export { webLightTheme, webDarkTheme, teamsDarkTheme };
