import { WS_BASE } from "./api";
import type { Mode, TurnEvent } from "./types";

export interface TurnRequest {
  session_id: string;
  path_id: string;
  mode: Mode;
  message: string;
  turn_id?: string;
}

/**
 * Run one tutor turn over the WebSocket and stream events back.
 * The answer to a question card is just the next turn's `message`.
 */
export function runTurn(
  request: TurnRequest,
  onEvent: (event: TurnEvent) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${WS_BASE}/ws`);
    ws.onopen = () => ws.send(JSON.stringify(request));
    ws.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as TurnEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onerror = () => reject(new Error("websocket error"));
    ws.onclose = () => resolve();
  });
}
