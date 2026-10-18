"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Modal } from "@/components/common/Modal";

export interface CreateTopicInput {
  name: string;
  goal: string;
  folder: string;
}

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
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState(false);

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
        <label className="block text-[12px] text-muted-foreground">
          {t("dash.sources")}（文件夹，可选）
          <input
            value={folder}
            onChange={(event) => setFolder(event.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </label>
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
              await onCreate({ name: name.trim(), goal: goal.trim(), folder: folder.trim() });
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
