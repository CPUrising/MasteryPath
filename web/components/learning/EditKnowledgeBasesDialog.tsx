"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Modal } from "@/components/common/Modal";
import { api } from "@/lib/api";
import { knowledgeApi } from "@/lib/knowledge-api";
import type { KnowledgeBase } from "@/lib/types";

/** Edit the default knowledge bases a mastery path runs on. */
export function EditKnowledgeBasesDialog({
  open,
  pathId,
  current,
  onClose,
  onSaved,
}: {
  open: boolean;
  pathId: string;
  current: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selected, setSelected] = useState<string[]>(current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setSelected(current);
    setError("");
    knowledgeApi.list().then(setKbs).catch(() => setKbs([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const toggle = (id: string) =>
    setSelected((values) => (values.includes(id) ? values.filter((v) => v !== id) : [...values, id]));

  return (
    <Modal open={open} title={t("kb.editDefaults")} onClose={onClose}>
      <div className="max-h-72 overflow-y-auto rounded-lg border border-border">
        {kbs.length === 0 ? (
          <p className="px-3 py-3 text-[12px] text-muted-foreground">{t("kb.empty.body")}</p>
        ) : (
          kbs.map((kb) => {
            const active = selected.includes(kb.id);
            return (
              <button
                key={kb.id}
                type="button"
                aria-pressed={active}
                onClick={() => toggle(kb.id)}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] ${
                  active ? "bg-accent" : "hover:bg-accent/50"
                }`}
              >
                <span
                  className={`h-3.5 w-3.5 shrink-0 rounded border ${
                    active ? "border-primary bg-primary" : "border-border"
                  }`}
                />
                <span className="min-w-0 flex-1 truncate">{kb.name}</span>
                <span className="shrink-0 text-[10px] text-muted-foreground">
                  {t(`kb.status.${kb.status}`, kb.status)}
                </span>
              </button>
            );
          })
        )}
      </div>
      {error && <p className="mt-2 text-[12px] text-destructive">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="h-9 rounded-lg border border-border px-3.5 text-[13px]">
          {t("common.cancel")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await api.setPathKnowledgeBases(pathId, selected);
              onSaved();
              onClose();
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : String(reason));
            } finally {
              setBusy(false);
            }
          }}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("settings.save")}
        </button>
      </div>
    </Modal>
  );
}
