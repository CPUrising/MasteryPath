import type { Mode, PathState, Provider, TopicSession } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return (await response.json()) as T;
}

const post = <T>(url: string, body: unknown) =>
  fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  }).then(json<T>);

const put = <T>(url: string, body: unknown) =>
  fetch(url, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  }).then(json<T>);

export const api = {
  listPaths: () =>
    fetch(`${API_BASE}/learning/paths`).then(
      json<{ path_id: string; name: string; goal: string; objectives: number }[]>,
    ),
  getState: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}`).then(json<PathState>),
  createPath: (pathId: string, goal: string, name = "") =>
    post<PathState>(`${API_BASE}/learning/paths`, { path_id: pathId, goal, name }),
  rename: (pathId: string, name: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name }),
    }).then(json<{ name: string }>),
  redo: (pathId: string) => post<{ status: string }>(`${API_BASE}/learning/paths/${pathId}/redo`, {}),
  remove: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}`, { method: "DELETE" }),
  putMap: (pathId: string, sessionId: string, body: unknown) =>
    put<{ status: string }>(
      `${API_BASE}/learning/paths/${pathId}/map?session_id=${encodeURIComponent(sessionId)}`,
      body,
    ),
  override: (pathId: string, kpId: string, note = "") =>
    post<{ source: string }>(
      `${API_BASE}/learning/paths/${pathId}/objectives/${kpId}/override`,
      { note },
    ),
  resolveGap: (pathId: string, gapId: string, action: "accept" | "regenerate") =>
    post<{ resolution: string }>(`${API_BASE}/learning/paths/${pathId}/gaps/${gapId}/resolve`, {
      action,
    }),
  setReviewSettings: (pathId: string, desiredRetention: number) =>
    put<{ desired_retention: number }>(
      `${API_BASE}/learning/paths/${pathId}/review-settings`,
      { desired_retention: desiredRetention },
    ),
  setMode: (pathId: string, sessionId: string, mode: Mode, actor = "learner") =>
    put<{ mode: Mode }>(
      `${API_BASE}/learning/paths/${pathId}/sessions/${sessionId}/mode`,
      { mode, actor },
    ),
  listSessions: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}/sessions`).then(
      json<{ sessions: TopicSession[] }>,
    ),
  getSession: (sessionId: string) =>
    fetch(`${API_BASE}/learning/sessions/${sessionId}`).then(
      json<{ session: TopicSession; messages: unknown[] }>,
    ),
  attachSources: (pathId: string, folder: string) =>
    post<unknown[]>(`${API_BASE}/learning/paths/${pathId}/sources`, { folder }),
  suggestQuestion: (pathId: string) =>
    fetch(`${API_BASE}/learning/paths/${pathId}/suggest-question`).then(
      json<{ suggestion: string }>,
    ),
  questions: (pathId: string, tag?: string) =>
    fetch(
      `${API_BASE}/learning/paths/${pathId}/questions${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`,
    ).then(json<unknown[]>),
  quiz: (pathId: string, body: unknown) =>
    post<{ question_id: string; question_card: unknown }>(`${API_BASE}/learning/paths/${pathId}/quiz`, body),
  grade: (pathId: string, body: unknown) =>
    post<{ status: string; result: string; gate_cleared: boolean }>(
      `${API_BASE}/learning/paths/${pathId}/grade`,
      body,
    ),
  assess: (pathId: string, body: unknown) =>
    post<{ passed: boolean }>(`${API_BASE}/learning/paths/${pathId}/assess`, body),
  skipQuestion: (pathId: string, questionId: string) =>
    post<{ status: string }>(`${API_BASE}/learning/paths/${pathId}/skip-question`, {
      question_id: questionId,
    }),

  // settings
  getSettings: (section: string) => fetch(`${API_BASE}/settings/${section}`).then(json<unknown>),
  putSettings: (section: string, value: unknown) =>
    put<unknown>(`${API_BASE}/settings/${section}`, value),
  getProviders: () => fetch(`${API_BASE}/settings/providers`).then(json<Provider[]>),
};

export type { Provider, TopicSession };
