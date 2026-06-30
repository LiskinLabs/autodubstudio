// Utility: join class names, filtering falsy values
export function cn(...inputs: (string | undefined | null | false)[]): string {
  return inputs.filter(Boolean).join(" ");
}

export const SPEAKER_COLORS: Record<string, string> = {
  SPEAKER_00: "rgba(0, 120, 212, 0.4)", // Blue
  SPEAKER_01: "rgba(209, 52, 56, 0.4)", // Red
  SPEAKER_02: "rgba(16, 124, 16, 0.4)", // Green
  SPEAKER_03: "rgba(255, 170, 68, 0.4)", // Yellow
  SPEAKER_04: "rgba(118, 118, 118, 0.4)", // Gray
  SPEAKER_05: "rgba(194, 57, 179, 0.4)", // Magenta
  default: "rgba(136, 136, 136, 0.4)",
};
