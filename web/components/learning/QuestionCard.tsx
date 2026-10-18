"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { PendingQuestion } from "@/lib/types";

/** A posed question card. Answering starts the next turn. */
export function QuestionCard({
  question,
  onAnswer,
  onSkip,
}: {
  question: PendingQuestion;
  onAnswer: (text: string) => void;
  onSkip: () => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");

  return (
    <div className="rounded-xl border border-primary/25 bg-primary/[0.05] p-4">
      {question.objective_name && (
        <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">
          {question.objective_name}
        </div>
      )}
      <p className="text-sm font-medium">{question.prompt}</p>
      {question.options.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {question.options.map((option) => (
            <li key={option.label}>
              <button
                type="button"
                onClick={() => onAnswer(option.label)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-left text-[13px] hover:border-primary/40"
              >
                <strong className="mr-2">{option.label}.</strong>
                {option.body}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-3 flex gap-2">
          <input
            value={text}
            placeholder={t("q.placeholder")}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && text.trim()) {
                event.preventDefault();
                onAnswer(text.trim());
                setText("");
              }
            }}
            className="flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring/40"
          />
          <button
            type="button"
            disabled={!text.trim()}
            onClick={() => {
              onAnswer(text.trim());
              setText("");
            }}
            className="rounded-lg bg-primary px-3.5 text-sm font-medium text-primary-foreground disabled:opacity-40"
          >
            {t("q.submit")}
          </button>
        </div>
      )}
      <div className="mt-3 text-right">
        <button type="button" onClick={onSkip} className="text-[12px] text-muted-foreground hover:underline">
          {t("q.skip")}
        </button>
      </div>
    </div>
  );
}
