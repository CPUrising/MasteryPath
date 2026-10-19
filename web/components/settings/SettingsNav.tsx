"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { settingsRoute } from "@/lib/learning-routes";

const GROUPS: { label: string; keys: string[] }[] = [
  { label: "settings.group.personal", keys: ["general"] },
  { label: "settings.group.models", keys: ["connections", "llm", "task-models", "embedding", "indexing"] },
];

const LABELS: Record<string, string> = {
  general: "settings.general.title",
  connections: "settings.conn.title",
  llm: "settings.llm.title",
  "task-models": "settings.task.title",
  embedding: "settings.embedding.title",
  indexing: "settings.indexing.title",
};

export function SettingsNav() {
  const { t } = useTranslation();
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const current = pathname.split("/")[2] || "general";

  return (
    <nav aria-label={t("settings.title")} className="flex h-full w-[240px] shrink-0 flex-col border-r border-border bg-card/40 px-2.5 py-4">
      <input
        aria-label={t("settings.search")}
        placeholder={t("settings.search")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className="mx-1 mb-3 rounded-full bg-muted px-3 py-2 text-[13px] outline-none"
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {GROUPS.map((group) => {
          const keys = group.keys.filter((key) => !needle || t(LABELS[key]).toLowerCase().includes(needle));
          if (keys.length === 0) return null;
          return (
            <div key={group.label} className="mb-1">
              <p className="px-2.5 pb-1.5 pt-4 text-[12px] font-medium text-muted-foreground">
                {t(group.label)}
              </p>
              <div className="space-y-0.5">
                {keys.map((key) => (
                  <Link
                    key={key}
                    href={settingsRoute(key)}
                    aria-current={current === key ? "page" : undefined}
                    className={`block rounded-lg px-2.5 py-2 text-[13px] ${
                      current === key ? "bg-accent font-medium" : "hover:bg-accent/60"
                    }`}
                  >
                    {t(LABELS[key])}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </nav>
  );
}
