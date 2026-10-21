"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, PencilRuler } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EditKnowledgeBasesDialog } from "@/components/learning/EditKnowledgeBasesDialog";
import { EditTopicRouteDialog } from "@/components/learning/EditTopicRouteDialog";
import { LearnerProfileCard } from "@/components/learning/LearnerProfileCard";
import { ModuleOutline } from "@/components/learning/ModuleOutline";
import { ProgressRing } from "@/components/learning/ProgressRing";
import { ReviewTrail } from "@/components/learning/ReviewTrail";
import { SessionCamp } from "@/components/learning/SessionCamp";
import { api } from "@/lib/api";
import { MASTERY_HOME, masterySessionRoute } from "@/lib/learning-routes";
import type { PathState, TopicSession } from "@/lib/types";

export default function MasteryTopicPage() {
  const params = useParams<{ pathId: string }>();
  const pathId = String(params.pathId || "");
  const router = useRouter();
  const { t } = useTranslation();
  const sessionId = useMemo(() => Math.random().toString(36).slice(2), []);
  const [state, setState] = useState<PathState | null>(null);
  const [sessions, setSessions] = useState<TopicSession[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [kbEditor, setKbEditor] = useState(false);
  const [confirm, setConfirm] = useState<"reset" | "delete" | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.getState(pathId));
      setSessions((await api.listSessions(pathId)).sessions);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "load failed");
    }
  }, [pathId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!state) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        {error ?? t("common.loading")}
      </div>
    );
  }

  const { counts, next } = state;
  const progress = counts.total ? counts.mastered / counts.total : 0;
  const noOutline = counts.total === 0;

  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-6xl flex-col px-6 py-6">
      <div className="flex items-center justify-between">
        <Link href={MASTERY_HOME} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("dash.back")}
        </Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setEditorOpen(true)}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-2.5 text-[12px]"
          >
            <PencilRuler className="h-3.5 w-3.5" />
            {t("dash.editModules")}
          </button>
          <button
            type="button"
            onClick={() => setConfirm("reset")}
            className="h-8 rounded-lg border border-border px-2.5 text-[12px]"
          >
            {t("dash.reset")}
          </button>
          <button
            type="button"
            onClick={() => setConfirm("delete")}
            className="h-8 rounded-lg border border-border px-2.5 text-[12px] text-destructive"
          >
            {t("dash.delete")}
          </button>
        </div>
      </div>

      <header className="mt-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold">{state.name || pathId}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{state.goal}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-muted-foreground">{t("kb.title")}</span>
            {state.knowledge_bases.length === 0 ? (
              <span className="text-[11px] text-muted-foreground">{t("kb.none")}</span>
            ) : (
              state.knowledge_bases.map((kb) => (
                <span key={kb.id} className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">
                  {kb.name}
                </span>
              ))
            )}
            <button
              type="button"
              onClick={() => setKbEditor(true)}
              className="text-[11px] text-primary hover:underline"
            >
              {t("common.edit")}
            </button>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-[13px] tabular-nums text-muted-foreground">
            {counts.mastered}/{counts.total} {t("dash.knowledgePoints")}
          </span>
          <ProgressRing value={progress} size={40} stroke={4} />
        </div>
      </header>

      <section className="mt-5 flex flex-col gap-3 border-y border-border py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-[12px] text-muted-foreground">{t("dash.next")}</div>
          <div className="truncate text-[14px] font-medium">
            {noOutline ? t("dash.designOutline") : next.knowledge_point_name || t("dash.celebrate")}
          </div>
          <p className="mt-0.5 truncate text-[12px] text-muted-foreground">
            {noOutline ? t("dash.noOutline.body") : next.reason}
          </p>
        </div>
        <Link
          href={masterySessionRoute(pathId, next.action === "review" ? "review" : noOutline ? "outline" : "study")}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground"
        >
          {noOutline ? t("dash.designOutline") : t("dash.continue")}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </section>

      <div className="mt-6 grid min-h-0 flex-1 gap-7 lg:grid-cols-[minmax(0,1fr)_320px]">
        {noOutline ? (
          <section className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border p-8 text-center">
            <h2 className="text-lg font-semibold">{t("dash.noOutline.title")}</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">{t("dash.noOutline.body")}</p>
            <Link
              href={masterySessionRoute(pathId, "outline")}
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground"
            >
              {t("dash.designWithTutor")}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </section>
        ) : (
          <div className="min-h-0 space-y-5 overflow-y-auto pr-1">
            <h2 className="text-[12px] font-semibold">{t("dash.masteryOutline")}</h2>
            <ModuleOutline
              map={state.map}
              onOverride={(kpId) => api.override(pathId, kpId).then(load)}
            />
          </div>
        )}

        <div className="space-y-5">
          <ReviewTrail
            reviews={state.reviews}
            desiredRetention={state.review_settings.desired_retention}
            onRetentionChange={(value) => api.setReviewSettings(pathId, value).then(load)}
            onStartReview={() => router.push(masterySessionRoute(pathId, "review"))}
          />
          <LearnerProfileCard profile={state.learner_profile} />
          <SessionCamp pathId={pathId} sessions={sessions} loading={false} />
        </div>
      </div>

      <EditKnowledgeBasesDialog
        open={kbEditor}
        pathId={pathId}
        current={state.knowledge_bases.map((kb) => kb.id)}
        onClose={() => setKbEditor(false)}
        onSaved={() => void load()}
      />

      <EditTopicRouteDialog
        open={editorOpen}
        initial='{"modules": []}'
        onClose={() => setEditorOpen(false)}
        onSave={async (modules) => {
          await api.setMode(pathId, sessionId, "outline");
          await api.putMap(pathId, sessionId, { modules, confirm: true });
          setEditorOpen(false);
          await load();
        }}
      />

      <ConfirmDialog
        open={confirm === "reset"}
        title={t("dash.reset")}
        description={t("dash.resetConfirm")}
        busy={busy}
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          setBusy(true);
          await api.redo(pathId);
          setBusy(false);
          setConfirm(null);
          await load();
        }}
      />
      <ConfirmDialog
        open={confirm === "delete"}
        title={t("dash.delete")}
        description={t("dash.deleteConfirm")}
        destructive
        busy={busy}
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          setBusy(true);
          await api.remove(pathId);
          router.replace(MASTERY_HOME);
        }}
      />
    </div>
  );
}
