import type { Mode, PathState } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export const api = {
  listPaths: () =>
    fetch(`${API_BASE}/learning/paths`).then(asJson<{ path_id: string; name: string }[]>),

  getState: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}`).then(asJson<PathState>),

  setMode: (pathId: string, sessionId: string, mode: Mode) =>
    fetch(`${API_BASE}/learning/paths/${pathId}/sessions/${sessionId}/mode`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mode, actor: "learner" }),
    }).then(asJson<{ mode: Mode }>),

  putMap: (pathId: string, sessionId: string, body: unknown) =>
    fetch(
      `${API_BASE}/learning/paths/${pathId}/map?session_id=${encodeURIComponent(sessionId)}`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      },
    ).then(asJson<{ status: string }>),

  override: (pathId: string, kpId: string, note = "") =>
    fetch(`${API_BASE}/learning/paths/${pathId}/objectives/${kpId}/override`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ note }),
    }).then(asJson<{ source: string }>),

  resolveGap: (pathId: string, gapId: string, action: "accept" | "regenerate") =>
    fetch(`${API_BASE}/learning/paths/${pathId}/gaps/${gapId}/resolve`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action }),
    }).then(asJson<{ resolution: string }>),

  suggestQuestion: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}/suggest-question`).then(
      asJson<{ suggestion: string }>,
    ),

  questions: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}/questions`).then(asJson<unknown[]>),

  events: (pathId: string, since = 0) =>
    fetch(`${API_BASE}/learning/paths/${pathId}/events?since=${since}`).then(
      asJson<{ event_type: string }[]>,
    ),
};
