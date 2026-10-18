import type { Mode } from "./types";

export const MASTERY_MODES: readonly Mode[] = ["outline", "study", "review"];
export const DEFAULT_MODE: Mode = "study";

export function normalizeMode(value: unknown): Mode {
  const candidate = String(value ?? "").trim().toLowerCase();
  return (MASTERY_MODES as readonly string[]).includes(candidate)
    ? (candidate as Mode)
    : DEFAULT_MODE;
}

export const MODE_LABELS: Record<Mode, string> = {
  outline: "mode.outline",
  study: "mode.study",
  review: "mode.review",
};

export const MODE_NOTES: Record<Mode, string> = {
  outline: "mode.note.outline",
  study: "",
  review: "mode.note.review",
};
