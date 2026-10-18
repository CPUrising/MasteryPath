"use client";

import { useTranslation } from "react-i18next";

import { LearningShell } from "./LearningShell";
import { TopicMapCard, type TopicCardData } from "./TopicMapCard";

export function TopicAtlas({
  topics,
  loading,
  error,
  onCreate,
  onRetry,
}: {
  topics: TopicCardData[];
  loading: boolean;
  error: string | null;
  onCreate: () => void;
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  return (
    <LearningShell
      title={t("atlas.title")}
      subtitle={t("atlas.subtitle")}
      action={
        <button
          type="button"
          onClick={onCreate}
          className="h-9 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground transition hover:opacity-90"
        >
          {t("atlas.new")}
        </button>
      }
    >
      {error && (
        <div role="alert" className="mb-5 flex items-center justify-between rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm">
          <span>{error}</span>
          <button type="button" onClick={onRetry} className="font-medium hover:underline">
            {t("common.retry")}
          </button>
        </div>
      )}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-28 animate-pulse rounded-xl border border-border bg-muted/50" />
          ))}
        </div>
      ) : topics.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topics.map((topic) => (
            <TopicMapCard key={topic.path_id} topic={topic} />
          ))}
        </div>
      ) : !error ? (
        <div className="rounded-xl border border-dashed border-border px-6 py-14 text-center">
          <h2 className="text-lg font-semibold">{t("atlas.empty.title")}</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
            {t("atlas.empty.body")}
          </p>
          <button
            type="button"
            onClick={onCreate}
            className="mt-5 h-9 rounded-lg bg-primary px-4 text-sm text-primary-foreground"
          >
            {t("atlas.empty.cta")}
          </button>
        </div>
      ) : null}
    </LearningShell>
  );
}
