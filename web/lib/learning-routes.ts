import type { Mode } from "./types";

export const MASTERY_HOME = "/learning/mastery";

export function masteryTopicRoute(pathId: string): string {
  return `${MASTERY_HOME}/${encodeURIComponent(pathId)}`;
}

export function masterySessionsRoute(pathId: string): string {
  return `${masteryTopicRoute(pathId)}/sessions`;
}

export function masterySessionRoute(pathId: string, mode: Mode): string {
  const params = mode === "study" ? "" : `?mode=${mode}`;
  return `${masterySessionsRoute(pathId)}${params}`;
}

export function settingsRoute(section: string): string {
  return `/settings/${section}`;
}
