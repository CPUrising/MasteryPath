"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { masterySessionsRoute } from "@/lib/learning-routes";
import type { TopicSession } from "@/lib/types";

export function SessionCamp({
  pathId,
  sessions,
  loading,
}: {
  pathId: string;
  sessions: TopicSession[];
  loading: boolean;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-[13px] font-semibold">{t("sessions.title")}</h3>
      {loading ? (
        <p className="mt-3 text-[12px] text-muted-foreground">{t("common.loading")}</p>
      ) : sessions.length === 0 ? (
        <div className="mt-3">
          <p className="text-[12px] text-muted-foreground">{t("sessions.none")}</p>
          <Link
            href={masterySessionsRoute(pathId)}
            className="mt-2 inline-block text-[12px] text-primary hover:underline"
          >
            {t("study.start")}
          </Link>
        </div>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {sessions.map((session) => (
            <li key={session.session_id} className="flex items-center gap-2 text-[12px]">
              <span className="min-w-0 flex-1 truncate">{session.title || session.session_id}</span>
              <code className="text-[10px] text-muted-foreground">{session.mode}</code>
              <Link href={masterySessionsRoute(pathId)} className="text-[11px] text-primary hover:underline">
                {t("sessions.open")}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
