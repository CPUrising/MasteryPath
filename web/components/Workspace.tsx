"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { runTurn } from "../lib/turn";
import type { Mode, PathState, TurnEvent } from "../lib/types";
import { ActivityDrawer } from "./ActivityDrawer";
import { Composer } from "./Composer";
import { ModeBar } from "./ModeBar";
import { OutlineTree } from "./OutlineTree";
import { ProgressRing } from "./ProgressRing";
import { SideViewer } from "./SideViewer";
import { Transcript, type TranscriptItem } from "./Transcript";

function newSessionId(): string {
  return Math.random().toString(36).slice(2);
}

export function Workspace({ pathId }: { pathId: string }) {
  const [state, setState] = useState<PathState | null>(null);
  const [mode, setMode] = useState<Mode>("outline");
  const [items, setItems] = useState<TranscriptItem[]>([]);
  const [activity, setActivity] = useState<TurnEvent[]>([]);
  const [suggestion, setSuggestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const sessionId = useMemo(newSessionId, []);

  const refresh = useCallback(async () => {
    const next = await api.getState(pathId);
    setState(next);
    try {
      setSuggestion((await api.suggestQuestion(pathId)).suggestion);
    } catch {
      /* suggestion is best-effort */
    }
    return next;
  }, [pathId]);

  useEffect(() => {
    refresh().catch(() => setState(null));
  }, [refresh]);

  const changeMode = useCallback(
    async (next: Mode) => {
      setMode(next);
      try {
        await api.setMode(pathId, sessionId, next);
      } catch {
        /* admission errors surface on the next turn */
      }
    },
    [pathId, sessionId],
  );

  const send = useCallback(
    async (message: string) => {
      setBusy(true);
      setItems((prev) => [...prev, { role: "user", text: message }]);
      let text = "";
      const cards: TranscriptItem[] = [];
      try {
        await runTurn({ session_id: sessionId, path_id: pathId, mode, message }, (event) => {
          setActivity((prev) => [...prev, event]);
          if (event.type === "text_delta") text += String(event.data.text ?? "");
          if (event.type === "tool_result") {
            const metadata = event.data.metadata as Record<string, unknown> | undefined;
            const card = metadata?.question_card as TranscriptItem["card"];
            if (card) {
              cards.push({ role: "tutor", text: String(event.data.content ?? ""), card });
            }
          }
        });
      } catch (error) {
        text += `\n[错误] ${String(error)}`;
      }
      setItems((prev) => [...prev, { role: "tutor", text }, ...cards]);
      await refresh().catch(() => undefined);
      setBusy(false);
    },
    [pathId, sessionId, mode, refresh],
  );

  if (!state) {
    return <main style={{ padding: 24 }}>加载中…（pathId: {pathId}）</main>;
  }

  const current = state.next;
  return (
    <main
      style={{
        display: "grid",
        gridTemplateColumns: "260px 1fr 300px",
        gap: 16,
        padding: 16,
        alignItems: "start",
      }}
    >
      <section>
        <h2 style={{ fontSize: 16, marginTop: 0 }}>{state.name || state.path_id}</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <ProgressRing value={current.mastery} />
          <div style={{ fontSize: 13 }}>
            <div>
              <strong>{current.knowledge_point_name || "—"}</strong>
            </div>
            <div style={{ color: "#6b7280" }}>{current.action}</div>
          </div>
        </div>
        <ModeBar mode={mode} onChange={changeMode} />
        <hr />
        <OutlineTree
          map={state.map}
          onOverride={(kpId) => api.override(pathId, kpId).then(refresh)}
        />
      </section>

      <section>
        <Transcript items={items} onAnswer={send} />
        <Composer suggestion={suggestion} onSend={send} disabled={busy} />
      </section>

      <section style={{ display: "flex", gap: 12 }}>
        <SideViewer
          state={state}
          onResolveGap={(gapId, action) =>
            api.resolveGap(pathId, gapId, action).then(refresh)
          }
        />
        <ActivityDrawer
          events={activity}
          open={drawerOpen}
          onToggle={() => setDrawerOpen((value) => !value)}
        />
      </section>
    </main>
  );
}
