"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Modal } from "@/components/common/Modal";
import { knowledgeApi } from "@/lib/knowledge-api";
import type { KnowledgeBase } from "@/lib/types";

export interface CreateTopicInput {
  name: string;
  goal: string;
  knowledgeBaseIds: string[];
}

/** Create a mastery topic, choosing its default knowledge bases. */
export function CreateTopicWizard({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (input: CreateTopicInput) => Promise<void> | void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    knowledgeApi.list().then(setKnowledgeBases).catch(() => setKnowledgeBases([]));
  }, [open]);

  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );

  return (
    <Modal open={open} title={t("atlas.new")} onClose={onClose}>
      <div className="space-y-3">
        <label className="block text-[12px] text-muted-foreground">
          {t("settings.provider.name")}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-[12px] text-muted-foreground">
          {t("atlas.subtitle")}
          <textarea
            rows={3}
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            className="mt-1 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </label>
        <div className="block text-[12px] text-muted-foreground">
          {t("kb.title")}
          <div className="mt-1 max-h-44 overflow-y-auto rounded-lg border border-border">
            {knowledgeBases.length === 0 ? (
              <p className="px-3 py-3 text-[12px] text-muted-foreground">{t("kb.empty.body")}</p>
            ) : (
              knowledgeBases.map((kb) => {
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
          <p className="mt-1 text-[11px] text-muted-foreground">{t("kb.folderSkip")}</p>
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="h-9 rounded-lg border border-border px-3.5 text-[13px]">
          {t("common.cancel")}
        </button>
        <button
          type="button"
          disabled={busy || !goal.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              await onCreate({ name: name.trim(), goal: goal.trim(), knowledgeBaseIds: selected });
            } finally {
              setBusy(false);
            }
          }}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("common.confirm")}
        </button>
      </div>
    </Modal>
  );
}
