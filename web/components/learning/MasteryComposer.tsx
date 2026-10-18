"use client";

import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

/** The study composer: Tab accepts the suggested question, Enter sends. */
export function MasteryComposer({
  placeholder,
  askHint,
  disabled,
  onSend,
}: {
  placeholder: string;
  askHint?: string;
  disabled?: boolean;
  onSend: (text: string) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  return (
    <div className="border-t border-border bg-background px-4 py-3">
      {askHint && !text && (
        <div className="mb-1.5 text-[12px] text-muted-foreground">
          {askHint} <span className="text-muted-foreground/60">（{t("study.tabHint")}）</span>
        </div>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={ref}
          rows={2}
          value={text}
          disabled={disabled}
          placeholder={askHint || placeholder}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Tab" && !text && askHint) {
              event.preventDefault();
              setText(askHint);
              return;
            }
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              const value = text.trim();
              if (!value) return;
              onSend(value);
              setText("");
            }
          }}
          className="min-h-[44px] flex-1 resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring/40"
        />
        <button
          type="button"
          disabled={disabled || !text.trim()}
          onClick={() => {
            const value = text.trim();
            if (!value) return;
            onSend(value);
            setText("");
          }}
          className="h-10 shrink-0 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-40"
        >
          {t("study.send")}
        </button>
      </div>
    </div>
  );
}
