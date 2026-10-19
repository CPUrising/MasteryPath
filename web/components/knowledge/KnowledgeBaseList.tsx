"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Database, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { LearningShell } from "@/components/learning/LearningShell";
import { CreateKnowledgeBaseModal } from "./CreateKnowledgeBaseModal";
import { knowledgeApi } from "@/lib/knowledge-api";
import { knowledgeBaseRoute } from "@/lib/learning-routes";
import type { KnowledgeBase } from "@/lib/types";

export function KnowledgeBaseList() {
  const { t } = useTranslation();
  const router = useRouter();
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setKbs(await knowledgeApi.list());
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <LearningShell
      title={t("nav.knowledge")}
      subtitle={t("kb.subtitle")}
      action={
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          <Plus size={15} />
          {t("kb.create")}
        </button>
      }
    >
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-28 animate-pulse rounded-xl border border-border bg-muted/50" />
          ))}
        </div>
      ) : kbs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border px-6 py-14 text-center">
          <Database size={22} className="mx-auto text-muted-foreground" />
          <h2 className="mt-3 text-lg font-semibold">{t("kb.empty.title")}</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{t("kb.empty.body")}</p>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="mt-5 h-9 rounded-lg bg-primary px-4 text-sm text-primary-foreground"
          >
            {t("kb.create")}
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {kbs.map((kb) => (
            <Link
              key={kb.id}
              href={knowledgeBaseRoute(kb.id)}
              className="rounded-xl border border-border bg-card p-4 transition hover:bg-accent/40"
            >
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-muted text-muted-foreground">
                  <Database size={13} />
                </span>
                <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{kb.name}</span>
              </div>
              <p className="mt-2 truncate text-[12px] text-muted-foreground">
                {kb.embedding_model?.name || t("kb.noEmbedding")}
                {kb.embedding_model?.dimension ? ` · ${kb.embedding_model.dimension}${t("kb.dim")}` : ""}
              </p>
              <p className="mt-1 flex items-center gap-2 text-[12px] text-muted-foreground">
                <span>{t("kb.docCount", { count: kb.doc_count })}</span>
                <span>· {t("kb.chunkCount", { count: kb.chunk_count })}</span>
                <span>· {t(`kb.status.${kb.status}`, kb.status)}</span>
              </p>
            </Link>
          ))}
        </div>
      )}
      <CreateKnowledgeBaseModal
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(id) => {
          setCreating(false);
          router.push(knowledgeBaseRoute(id));
        }}
      />
    </LearningShell>
  );
}
