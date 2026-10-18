"use client";

import { useTranslation } from "react-i18next";

const FIELDS: [string, string][] = [
  ["prior_knowledge", "已掌握"],
  ["target_level", "目标"],
  ["time_budget", "时间"],
  ["preferences", "偏好"],
];

export function LearnerProfileCard({
  profile,
}: {
  profile: Record<string, string> | null;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-[13px] font-semibold">{t("profile.title")}</h3>
      {!profile || Object.values(profile).every((value) => !value) ? (
        <p className="mt-3 text-[12px] text-muted-foreground">{t("profile.empty")}</p>
      ) : (
        <dl className="mt-3 space-y-1.5 text-[12px]">
          {FIELDS.map(([key, label]) =>
            profile[key] ? (
              <div key={key} className="flex gap-2">
                <dt className="w-14 shrink-0 text-muted-foreground">{label}</dt>
                <dd className="min-w-0 flex-1">{profile[key]}</dd>
              </div>
            ) : null,
          )}
        </dl>
      )}
    </section>
  );
}
