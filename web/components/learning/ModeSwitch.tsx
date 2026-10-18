"use client";

import { useTranslation } from "react-i18next";

import { MASTERY_MODES, MODE_LABELS } from "@/lib/mastery-mode";
import type { Mode } from "@/lib/types";

/** All three modes, with the live one marked. */
export function ModeSwitch({
  mode,
  onSelect,
  disabled,
}: {
  mode: Mode;
  onSelect: (mode: Mode) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t("mode.study")}
      className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5"
    >
      {MASTERY_MODES.map((candidate) => {
        const active = candidate === mode;
        return (
          <button
            key={candidate}
            type="button"
            disabled={disabled || active}
            aria-pressed={active}
            onClick={() => !active && onSelect(candidate)}
            className={`flex h-7 items-center gap-1.5 rounded-md px-2 text-[12px] font-medium transition ${
              active
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            } disabled:cursor-default`}
          >
            <span
              aria-hidden
              className={`h-[7px] w-[7px] rounded-full border ${
                active ? "border-primary bg-primary" : "border-muted-foreground/45"
              }`}
            />
            {t(MODE_LABELS[candidate])}
          </button>
        );
      })}
    </div>
  );
}
