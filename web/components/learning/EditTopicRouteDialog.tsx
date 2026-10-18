"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Modal } from "@/components/common/Modal";

/** Edit the outline by pasting a modules payload (progress-preserving revise). */
export function EditTopicRouteDialog({
  open,
  initial,
  onClose,
  onSave,
}: {
  open: boolean;
  initial: string;
  onClose: () => void;
  onSave: (modules: unknown[]) => Promise<void> | void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState(initial);
  const [error, setError] = useState("");

  return (
    <Modal open={open} title={t("dash.editModules")} onClose={onClose}>
      <p className="mb-2 text-[12px] text-muted-foreground">
        {"[{\"name\": \"模块\", \"knowledge_points\": [{\"name\": \"目标\", \"type\": \"concept\"}]}]"}
      </p>
      <textarea
        rows={10}
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 font-mono text-[12px]"
      />
      {error && <p className="mt-2 text-[12px] text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="h-9 rounded-lg border border-border px-3.5 text-[13px]">
          {t("common.cancel")}
        </button>
        <button
          type="button"
          onClick={async () => {
            try {
              const parsed = JSON.parse(text);
              const modules = Array.isArray(parsed) ? parsed : parsed.modules;
              if (!Array.isArray(modules)) throw new Error("modules must be an array");
              await onSave(modules);
            } catch (reason) {
              setError(String(reason));
            }
          }}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground"
        >
          {t("common.save")}
        </button>
      </div>
    </Modal>
  );
}
