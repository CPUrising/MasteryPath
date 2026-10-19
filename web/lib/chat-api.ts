import { API_BASE } from "./api";
import type { ChatSessionDetail, ChatSessionSummary, ChatTurnEvent } from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return (await response.json()) as T;
}

export const chatApi = {
  list: () => fetch(`${API_BASE}/chat/sessions`).then(json<ChatSessionSummary[]>),
  create: (body: { title?: string; model_id?: string; kb_ids?: string[] } = {}) =>
    fetch(`${API_BASE}/chat/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<ChatSessionSummary>),
  get: (sessionId: string) =>
    fetch(`${API_BASE}/chat/sessions/${sessionId}`).then(json<ChatSessionDetail>),
  update: (sessionId: string, body: Partial<Pick<ChatSessionSummary, "title" | "model_id" | "kb_ids">>) =>
    fetch(`${API_BASE}/chat/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<ChatSessionSummary>),
  remove: (sessionId: string) =>
    fetch(`${API_BASE}/chat/sessions/${sessionId}`, { method: "DELETE" }),
  /** Stream one turn over SSE; resolves when the stream ends. */
  async streamTurn(
    sessionId: string,
    message: string,
    attachments: { name: string }[],
    onEvent: (event: ChatTurnEvent) => void,
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}/turns`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message, attachments }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`${response.status}: ${await response.text().catch(() => "")}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame.split("\n").find((row) => row.startsWith("data:"));
        if (!line) continue;
        try {
          onEvent(JSON.parse(line.slice(5).trim()) as ChatTurnEvent);
        } catch {
          /* ignore malformed frames */
        }
      }
    }
  },
};
