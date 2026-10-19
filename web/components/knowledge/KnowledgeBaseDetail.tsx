"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, RefreshCw, Trash2, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";

import { knowledgeApi } from "@/lib/knowledge-api";
import { KNOWLEDGE_HOME } from "@/lib/learning-routes";
import type { KnowledgeBase, KnowledgeFile, KnowledgeProgress } from "@/lib/types";

type Tab = "documents" | "folders" | "settings";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-2.5 last:border-0 sm:flex-row sm:items-center">
      <span className="w-40 shrink-0 text-[12px] text-muted-foreground">{label}</span>
      <span className="break-all text-[13px]">{value || "—"}</span>
    </div>
  );
}

function IndexProgress({ progress }: { progress: KnowledgeProgress }) {
  const { t } = useTranslation();
  const percent = progress.percent;
  return (
    <div className="mt-3 rounded-xl border border-border p-3">
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
        <Loader2 size={13} className="animate-spin" />
        <span>
          {t("kb.indexing", {
            indexed: progress.indexed_files,
            total: progress.total_files,
          })}
          {percent != null ? `（${Math.round(percent * 100)}%）` : ""}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        {percent == null ? (
          <div className="h-full w-1/3 animate-pulse rounded-full bg-primary" />
        ) : (
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent * 100}%` }} />
        )}
      </div>
    </div>
  );
}

export function KnowledgeBaseDetail({ kbId }: { kbId: string }) {
  const { t } = useTranslation();
  const router = useRouter();
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [progress, setProgress] = useState<KnowledgeProgress | null>(null);
  const [tab, setTab] = useState<Tab>("documents");
  const [folder, setFolder] = useState("");
  const [folderMode, setFolderMode] = useState<"import" | "link">("import");
  const [chunkSize, setChunkSize] = useState(512);
  const [chunkOverlap, setChunkOverlap] = useState(64);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const dirRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    dirRef.current?.setAttribute("webkitdirectory", "");
  }, []);

  const load = useCallback(async () => {
    try {
      const [detail, list, state] = await Promise.all([
        knowledgeApi.get(kbId),
        knowledgeApi.files(kbId),
        knowledgeApi.progress(kbId).catch(() => null),
      ]);
      setKb(detail);
      setFiles(list);
      setProgress(state);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [kbId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!kb) return;
    setChunkSize(kb.effective_config?.chunk_size ?? 512);
    setChunkOverlap(kb.effective_config?.chunk_overlap ?? 64);
  }, [kb]);

  // Poll while an index run is in flight; stop the moment it leaves "indexing".
  useEffect(() => {
    if (kb?.status !== "indexing") return;
    let cancelled = false;
    const tick = async () => {
      try {
        const state = await knowledgeApi.progress(kbId);
        if (cancelled) return;
        setProgress(state);
        if (state.status !== "indexing") await load();
      } catch {
        /* keep polling; load() surfaces persistent errors */
      }
    };
    const timer = window.setInterval(() => void tick(), 1000);
    void tick();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [kb?.status, kbId, load]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action();
      setKb((current) => (current ? { ...current, status: "indexing" } : current));
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const upload = async (list: File[]) => {
    if (!list.length) return;
    const paths = list.map(
      (file) => (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
    );
    await run(() => knowledgeApi.upload(kbId, list, paths));
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
          disabled={busy || kb.status === "indexing"}
          onClick={() => void run(() => knowledgeApi.reindex(kb.id))}
          className={`inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-[13px] disabled:opacity-50 ${
            kb.needs_reindex ? "border-primary text-primary" : "border-border"
          }`}
        >
          <RefreshCw size={14} className={kb.status === "indexing" ? "animate-spin" : ""} />
          {t("kb.reindex")}
        </button>
      </header>

      {kb.status === "indexing" && progress && <IndexProgress progress={progress} />}
      {kb.status === "empty" && !kb.doc_count && (
        <p className="mt-3 rounded-xl border border-dashed border-border px-4 py-3 text-[13px] text-muted-foreground">
          {t("kb.empty.body")}
        </p>
      )}
      {kb.skipped_count > 0 && (
        <p className="mt-3 text-[12px] text-amber-600 dark:text-amber-400">
          {t("kb.skipped", { count: kb.skipped_count })}
        </p>
      )}

      <nav className="mt-5 flex gap-1 border-b border-border pb-2">
        {tabButton("documents", t("kb.tab.documents"))}
        {tabButton("folders", t("kb.tab.folders"))}
        {tabButton("settings", t("kb.tab.settings"))}
      </nav>

      {error && <p className="mt-4 text-[13px] text-destructive">{error}</p>}

      {tab === "documents" && (
        <section className="mt-5 space-y-4">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || kb.status === "indexing"}
              onClick={() => fileRef.current?.click()}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
            >
              <Upload size={14} />
              {t("kb.upload")}
            </button>
            <button
              type="button"
              disabled={busy || kb.status === "indexing"}
              onClick={() => dirRef.current?.click()}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border px-3.5 text-[13px] disabled:opacity-50"
            >
              {t("kb.uploadFolder")}
            </button>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".txt,.md,.markdown"
              hidden
              onChange={(event) => void upload(Array.from(event.target.files ?? []))}
            />
            <input
              ref={dirRef}
              type="file"
              multiple
              hidden
              onChange={(event) => void upload(Array.from(event.target.files ?? []))}
            />
          </div>
          {files.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">{t("kb.noFiles")}</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {files.map((file) => (
                <li key={file.path} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="min-w-0 flex-1 truncate text-[13px]">{file.path}</span>
                  {file.linked && (
                    <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {t("kb.linked")}
                    </span>
                  )}
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {Math.max(1, Math.round(file.size / 1024))} KB
                  </span>
                  {!file.linked && (
                    <button
                      type="button"
                      aria-label={t("common.remove")}
                      disabled={busy}
                      onClick={() => void run(() => knowledgeApi.removeFile(kb.id, file.path))}
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
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
              <Row label={t("kb.documents")} value={t("kb.docCount", { count: kb.doc_count })} />
              <Row label={t("kb.chunks")} value={t("kb.chunkCount", { count: kb.chunk_count })} />
              <Row
                label={t("kb.chunkSize")}
                value={`${kb.effective_config?.chunk_size ?? "-"} ${t("kb.tokens")}`}
              />
              <Row
                label={t("kb.chunkOverlap")}
                value={`${kb.effective_config?.chunk_overlap ?? "-"} ${t("kb.tokens")}`}
              />
              <Row
                label={t("kb.configSource")}
                value={t(`kb.source.${kb.index_config_source}`)}
              />
              <Row
                label={t("kb.indexedConfig")}
                value={
                  kb.indexed_config?.chunk_size != null
                    ? `${kb.indexed_config.chunk_size} / ${kb.indexed_config.chunk_overlap}`
                    : t("kb.indexedUnknown")
                }
              />
              <Row label={t("kb.created")} value={kb.created_at_iso} />
              <Row label={t("kb.updated")} value={kb.updated_at_iso} />
              <Row label={t("kb.lastIndexed")} value={kb.last_indexed_at_iso} />
              <Row label={t("kb.diskPath")} value={kb.disk_path} />
            </div>
          </div>
          <div className="border-t border-border pt-4">
            <p className="text-[13px] font-medium">{t("kb.chunkSettings")}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="block text-[12px] text-muted-foreground">
                {t("kb.chunkSize")}
                <select
                  value={chunkSize}
                  disabled={busy || kb.status === "indexing"}
                  onChange={(event) => setChunkSize(Number(event.target.value))}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm disabled:opacity-50"
                >
                  {[512, 800, 1024, 1536].map((size) => (
                    <option key={size} value={size}>
                      {size} {t("kb.tokens")}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-[12px] text-muted-foreground">
                {t("kb.chunkOverlap")}
                <select
                  value={chunkOverlap}
                  disabled={busy || kb.status === "indexing"}
                  onChange={(event) => setChunkOverlap(Number(event.target.value))}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm disabled:opacity-50"
                >
                  {[0, 64, 100, 128, 200].map((overlap) => (
                    <option key={overlap} value={overlap}>
                      {overlap} {t("kb.tokens")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {kb.needs_reindex && (
              <p className="mt-2 text-[12px] text-amber-600 dark:text-amber-400">
                {t("kb.needsReindex")}
              </p>
            )}
            <button
              type="button"
              disabled={
                busy ||
                kb.status === "indexing" ||
                chunkOverlap >= chunkSize ||
                (chunkSize === kb.effective_config?.chunk_size &&
                  chunkOverlap === kb.effective_config?.chunk_overlap)
              }
              onClick={() =>
                void run(() => knowledgeApi.update(kb.id, { chunk_size: chunkSize, chunk_overlap: chunkOverlap }))
              }
              className="mt-3 h-9 rounded-lg border border-border px-3.5 text-[13px] disabled:opacity-50"
            >
              {t("kb.saveChunkSettings")}
            </button>
            {chunkOverlap >= chunkSize && (
              <p className="mt-2 text-[12px] text-destructive">{t("kb.chunkInvalid")}</p>
            )}
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
