"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Modal } from "@/components/common/Modal";
import { Field, TextInput } from "@/components/settings/shared";
import { api } from "@/lib/api";
import { knowledgeApi } from "@/lib/knowledge-api";
import type { ModelSection } from "@/lib/types";

export interface CreateKnowledgeInput {
  name: string;
  description: string;
  mode: "import" | "link";
  embedding_model_id: string;
  folder: string;
}

export function CreateKnowledgeBaseModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (kbId: string) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [embeddingId, setEmbeddingId] = useState("");
  const [embeddings, setEmbeddings] = useState<ModelSection>({ models: [], active_id: "" });
  const [mode, setMode] = useState<"import" | "link">("import");
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    api
      .getSettings("embedding")
      .then((value) => {
        const section = value as ModelSection;
        setEmbeddings(section);
        setEmbeddingId(section.active_id || section.models?.[0]?.id || "");
      })
      .catch(() => setEmbeddings({ models: [], active_id: "" }));
  }, [open]);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const kb = await knowledgeApi.create({
        name: name.trim(),
        description: description.trim(),
        mode,
        embedding_model_id: embeddingId || undefined,
      });
      if (folder.trim()) {
        await knowledgeApi.addFolder(kb.id, folder.trim(), mode).catch((reason) => {
          setError(reason instanceof Error ? reason.message : String(reason));
        });
      }
      onCreated(kb.id);
      setName("");
      setDescription("");
      setFolder("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title={t("kb.create")} onClose={onClose}>
      <div className="space-y-3">
        <Field label={t("settings.provider.name")}>
          <TextInput value={name} onChange={setName} />
        </Field>
        <Field label={t("kb.description")}>
          <TextInput value={description} onChange={setDescription} />
        </Field>
        <Field label={t("kb.embedding")}>
          <select
            value={embeddingId}
            onChange={(event) => setEmbeddingId(event.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            {embeddings.models.length === 0 && <option value="">{t("kb.noEmbedding")}</option>}
            {embeddings.models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name || model.model}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("kb.mode")}>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as "import" | "link")}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="import">{t("kb.mode.import")}</option>
            <option value="link">{t("kb.mode.link")}</option>
          </select>
        </Field>
        <Field label={t("kb.folder")}>
          <TextInput value={folder} onChange={setFolder} />
        </Field>
        <p className="text-[12px] text-muted-foreground">{t("kb.folderSkip")}</p>
        {error && <p className="text-[12px] text-destructive">{error}</p>}
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="h-9 rounded-lg border border-border px-3.5 text-[13px]">
          {t("common.cancel")}
        </button>
        <button
          type="button"
          disabled={busy || !name.trim()}
          onClick={() => void submit()}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        >
          {busy ? t("common.loading") : t("settings.continue")}
        </button>
      </div>
    </Modal>
  );
}
