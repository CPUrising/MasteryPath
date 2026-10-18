"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";

import { LevelUpCelebration } from "@/components/learning/LevelUpCelebration";
import { MasteryComposer } from "@/components/learning/MasteryComposer";
import { ModeSwitch } from "@/components/learning/ModeSwitch";
import { ProgressRing } from "@/components/learning/ProgressRing";
import { QuestionCard } from "@/components/learning/QuestionCard";
import { StudyOutline } from "@/components/learning/StudyOutline";
import { api } from "@/lib/api";
import { masteryTopicRoute } from "@/lib/learning-routes";
import { MODE_NOTES, normalizeMode } from "@/lib/mastery-mode";
import type { Mode, PathState } from "@/lib/types";
import { runTurn } from "@/lib/ws";

interface Item {
  role: "user" | "assistant";
  text: string;
}

function masteredIds(state: PathState): Set<string> {
  return new Set(
    Object.entries(state.map)
      .filter(([, entry]) => entry.status === "mastered")
      .map(([kpId]) => kpId),
  );
}

function StudyRoute() {
  const params = useParams<{ pathId: string }>();
  const pathId = String(params.pathId || "");
  const search = useSearchParams();
  const { t } = useTranslation();
  const sessionId = useMemo(() => Math.random().toString(36).slice(2), []);

  const [state, setState] = useState<PathState | null>(null);
  const [mode, setMode] = useState<Mode>(normalizeMode(search.get("mode")));
  const [items, setItems] = useState<Item[]>([]);
  const [askHint, setAskHint] = useState("");
  const [busy, setBusy] = useState(false);
  const [outlineOpen, setOutlineOpen] = useState(true);
  const [celebration, setCelebration] = useState<string | null>(null);

  const load = useCallback(async () => {
    const next = await api.getState(pathId);
    setState((previous) => {
      if (previous) {
        const before = masteredIds(previous);
        const after = masteredIds(next);
        for (const kpId of after) {
          if (!before.has(kpId)) {
            setCelebration(kpId);
            break;
          }
        }
      }
      return next;
    });
    try {
      setAskHint((await api.suggestQuestion(pathId)).suggestion);
    } catch {
      /* suggestion is best-effort */
    }
  }, [pathId]);

  useEffect(() => {
    void load();
  }, [load]);

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
    async (text: string) => {
      setBusy(true);
      setItems((previous) => [...previous, { role: "user", text }]);
      let assistant = "";
      try {
        await runTurn({ session_id: sessionId, path_id: pathId, mode, message: text }, (event) => {
          if (event.type === "text_delta") assistant += String(event.data.text ?? "");
        });
      } catch (reason) {
        assistant = `${t("study.noProvider")} (${String(reason)})`;
      }
      setItems((previous) => [...previous, { role: "assistant", text: assistant }]);
      await load().catch(() => undefined);
      setBusy(false);
    },
    [pathId, sessionId, mode, load, t],
  );

  if (!state) {
    return <div className="flex h-full items-center justify-center text-muted-foreground">{t("common.loading")}</div>;
  }

  const { counts, next, pending_question } = state;
  const progress = counts.total ? counts.mastered / counts.total : 0;
  const note = MODE_NOTES[mode];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3">
        <Link href={masteryTopicRoute(pathId)} aria-label={t("dash.back")} className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/60">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-semibold">{state.name || pathId}</div>
          <div className="truncate text-[12px] text-muted-foreground">{next.knowledge_point_name}</div>
        </div>
        <ModeSwitch mode={mode} onSelect={changeMode} disabled={busy} />
        <div className="flex items-center gap-1.5 pl-2">
          <ProgressRing value={progress} size={18} stroke={2} showLabel={false} />
          <span className="text-[12px] tabular-nums text-muted-foreground">
            {counts.mastered}/{counts.total}
          </span>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className={`hidden shrink-0 overflow-y-auto border-r border-border bg-card/30 transition-[width] xl:block ${outlineOpen ? "w-[252px] px-5 py-5" : "w-9"}`}>
          <StudyOutline
            map={state.map}
            currentPointId={next.knowledge_point_id}
            justMasteredId={celebration}
            collapsed={!outlineOpen}
            onToggleCollapsed={() => setOutlineOpen((value) => !value)}
          />
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-3xl px-5 py-6">
              {note && (
                <p className="mb-5 rounded-lg border border-border bg-secondary px-3.5 py-2.5 text-[12px] text-muted-foreground">
                  {t(note)}
                </p>
              )}
              {items.length === 0 && !pending_question ? (
                <div className="flex min-h-[45vh] flex-col items-center justify-center text-center">
                  <div className="text-[12px] text-muted-foreground">{t("dash.next")}</div>
                  <h2 className="mt-1.5 text-xl font-semibold">{next.knowledge_point_name || t("dash.celebrate")}</h2>
                  <p className="mt-2 max-w-lg text-sm text-muted-foreground">{t("dash.noOutline.body")}</p>
                </div>
              ) : (
                <div className="space-y-5">
                  {items.map((item, index) => (
                    <div
                      key={index}
                      className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3.5 py-2.5 text-sm ${
                        item.role === "user" ? "ml-auto bg-primary/10" : "bg-muted"
                      }`}
                    >
                      {item.text}
                    </div>
                  ))}
                  {pending_question && (
                    <QuestionCard
                      question={pending_question}
                      onAnswer={async (answer) => {
                        await api.grade(pathId, { question_id: pending_question.question_id, answer });
                        await load();
                      }}
                      onSkip={async () => {
                        await api.skipQuestion(pathId, pending_question.question_id);
                        await load();
                      }}
                    />
                  )}
                </div>
              )}
            </div>
          </div>
          <MasteryComposer
            placeholder={t("study.placeholder")}
            askHint={askHint}
            disabled={busy}
            onSend={send}
          />
        </section>
      </div>

      {celebration && <LevelUpCelebration onDone={() => setCelebration(null)} />}
    </div>
  );
}

export default function MasteryStudyPage() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center text-muted-foreground">…</div>}>
      <StudyRoute />
    </Suspense>
  );
}
