"use client";

import { useTranslation } from "react-i18next";

import type { ReviewItem } from "@/lib/types";

export function ReviewTrail({
  reviews,
  desiredRetention,
  busy,
  onRetentionChange,
  onStartReview,
}: {
  reviews: ReviewItem[];
  desiredRetention: number;
  busy?: boolean;
  onRetentionChange: (value: number) => void;
  onStartReview: (kpId: string, name: string) => void;
}) {
  const { t } = useTranslation();
  const due = reviews.filter((review) => review.due);
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-semibold">{t("review.title")}</h3>
        <span className="text-[11px] text-muted-foreground">
          {due.length}/{reviews.length}
        </span>
      </div>

      <label className="mt-3 block text-[11px] text-muted-foreground">
        {t("review.retention")}: {desiredRetention.toFixed(2)}
        <input
          type="range"
          min={0.7}
          max={0.99}
          step={0.01}
          value={desiredRetention}
          disabled={busy}
          onChange={(event) => onRetentionChange(Number(event.target.value))}
          className="mt-1 w-full"
        />
      </label>

      {reviews.length === 0 ? (
        <p className="mt-3 text-[12px] text-muted-foreground">{t("review.none")}</p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {reviews.slice(0, 8).map((review) => (
            <li key={review.id} className="flex items-center gap-2 text-[12px]">
              <span
                aria-hidden
                className={`h-[7px] w-[7px] rounded-full ${
                  review.due ? "bg-primary" : "border border-muted-foreground/40"
                }`}
              />
              <span className="min-w-0 flex-1 truncate">{review.knowledge_point_name}</span>
              {review.due && (
                <button
                  type="button"
                  onClick={() => onStartReview(review.knowledge_point_id, review.knowledge_point_name)}
                  className="text-[11px] text-primary hover:underline"
                >
                  {t("review.start")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
