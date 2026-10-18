"use client";

import { useTranslation } from "react-i18next";

import { Modal } from "./Modal";

export function ConfirmDialog({
  open,
  title,
  description,
  destructive,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  description: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Modal open={open} title={title} onClose={onClose}>
      <p className="text-sm text-muted-foreground">{description}</p>
      <div className="mt-5 flex justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="h-9 rounded-lg border border-border px-3.5 text-[13px]"
        >
          {t("common.cancel")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onConfirm}
          className={`h-9 rounded-lg px-3.5 text-[13px] font-medium text-white disabled:opacity-50 ${
            destructive ? "bg-destructive" : "bg-primary"
          }`}
        >
          {t("common.confirm")}
        </button>
      </div>
    </Modal>
  );
}
