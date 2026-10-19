"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { knowledgeApi } from "@/lib/knowledge-api";
import { KNOWLEDGE_HOME } from "@/lib/learning-routes";
import type { KnowledgeBase, KnowledgeFile } from "@/lib/types";

type Tab = "documents" | "folders" | "settings";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-2.5 last:border-0 sm:flex-row sm:items-center">
      <span className="w-40 shrink-0 text-[12px] text-muted-foreground">{label}</span>
      <span className="break-all text-[13px]">{value || "—"}</span>
    </div>
  );
}

export function KnowledgeBaseDetail({ kbId }: { kbId: string }) {
  const { t } = useTranslation();
  const router = useRouter();
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [tab, setTab] = useState<Tab>("documents");
  const [folder, setFolder] = useState("");
  const [folderMode, setFolderMode] = useState<"import" | "link">("import");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [detail, list] = await Promise.all([
        knowledgeApi.get(kbId),
        knowledgeApi.files(kbId),
      ]);
      setKb(detail);
      setFiles(list);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [kbId]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  if (!kb) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-8">
        <p className="text-sm text-muted-foreground">{error || t("common.loading")}</p>
      </div>
    );
  }

  const statusTone =
    kb.status === "ready"
      ? "text-emerald-600 dark:text-emerald-400"
      : kb.status === "error"
        ? "text-destructive"
        : "text-amber-600 dark:text-amber-400";

  const tabButton = (key: Tab, label: string) => (
    <button
      key={key}
      type="button"
      onClick={() => setTab(key)}
      className={`h-9 rounded-lg px-3 text-[13px] ${
        tab === key ? "bg-accent font-medium" : "text-muted-foreground hover:bg-accent/50"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-7">
      <Link
        href={KNOWLEDGE_HOME}
        className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft size={15} />
        {t("nav.knowledge")}
      </Link>

      <header className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight">{kb.name}</h1>
          <p className={`mt-1 text-[13px] ${statusTone}`}>
            {t(`kb.status.${kb.status}`, kb.status)}
            {kb.error ? ` · ${kb.error}` : ""}
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => void run(() => knowledgeApi.reindex(kb.id))}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border px-3 text-[13px] disabled:opacity-50"
        >
          <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
          {t("kb.reindex")}
        </button>
      </header>

      <nav className="mt-5 flex gap-1 border-b border-border pb-2">
        {tabButton("documents", t("kb.tab.documents"))}
        {tabButton("folders", t("kb.tab.folders"))}
        {tabButton("settings", t("kb.tab.settings"))}
      </nav>

      {error && <p className="mt-4 text-[13px] text-destructive">{error}</p>}

      {tab === "documents" && (
        <section className="mt-5">
          {files.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">{t("kb.noFiles")}</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {files.map((file) => (
                <li key={file.path} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="min-w-0 flex-1 truncate text-[13px]">{file.path}</span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {Math.max(1, Math.round(file.size / 1024))} KB
                  </span>
                  <button
                    type="button"
                    aria-label={t("common.remove")}
                    disabled={busy}
                    onClick={() => void run(() => knowledgeApi.removeFile(kb.id, file.path))}
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "folders" && (
        <section className="mt-5 space-y-5">
          <div className="rounded-xl border border-border p-4">
            <p className="text-[13px] font-medium">{t("kb.addFolder")}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                value={folder}
                onChange={(event) => setFolder(event.target.value)}
                placeholder={t("kb.folderPlaceholder")}
                className="min-w-[220px] flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm"
              />
              <select
                value={folderMode}
                onChange={(event) => setFolderMode(event.target.value as "import" | "link")}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="import">{t("kb.mode.import")}</option>
                <option value="link">{t("kb.mode.link")}</option>
              </select>
              <button
                type="button"
                disabled={busy || !folder.trim()}
                onClick={() =>
                  void run(async () => {
                    await knowledgeApi.addFolder(kb.id, folder.trim(), folderMode);
                    setFolder("");
                  })
                }
                className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
              >
                {t("common.add")}
              </button>
            </div>
          </div>
          {kb.linked_folders.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">{t("kb.noLinkedFolders")}</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {kb.linked_folders.map((item) => (
                <li key={item.id} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="min-w-0 flex-1 truncate text-[13px]">{item.path}</span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {t("kb.docCount", { count: item.file_count })}
                  </span>
                  <button
                    type="button"
                    aria-label={t("common.remove")}
                    disabled={busy}
                    onClick={() => void run(() => knowledgeApi.removeFolder(kb.id, item.id))}
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "settings" && (
        <section className="mt-5 space-y-6">
          <div>
            <p className="text-[13px] font-medium">{t("kb.overview")}</p>
            <p className="mt-0.5 text-[12px] text-muted-foreground">{t("kb.overviewHint")}</p>
            <div className="mt-3 rounded-xl border border-border px-4 py-1">
              <Row label={t("kb.ragProvider")} value={kb.rag_provider} />
              <Row
                label={t("kb.embedding")}
                value={
                  kb.embedding_model?.name
                    ? `${kb.embedding_model.name}${
                        kb.embedding_model.dimension ? ` · ${kb.embedding_model.dimension}${t("kb.dim")}` : ""
                      }`
                    : t("kb.noEmbedding")
                }
              />
              <Row label={t("kb.created")} value={kb.created_at_iso} />
              <Row label={t("kb.updated")} value={kb.updated_at_iso} />
              <Row label={t("kb.lastIndexed")} value={kb.last_indexed_at_iso} />
              <Row label={t("kb.diskPath")} value={kb.disk_path} />
            </div>
          </div>
          <div className="flex items-center gap-3 border-t border-border pt-4">
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                if (window.confirm(t("kb.deleteConfirm", { name: kb.name }))) {
                  void run(async () => {
                    await knowledgeApi.remove(kb.id);
                    router.push(KNOWLEDGE_HOME);
                  });
                }
              }}
              className="inline-flex items-center gap-1.5 text-[13px] text-destructive hover:underline"
            >
              <Trash2 size={14} />
              {t("kb.delete")}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
