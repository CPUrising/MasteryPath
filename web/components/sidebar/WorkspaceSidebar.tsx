"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/lib/api";
import { MASTERY_HOME, masteryTopicRoute, settingsRoute } from "@/lib/learning-routes";

interface TopicLabel {
  path_id: string;
  name: string;
}

export function WorkspaceSidebar() {
  const { t } = useTranslation();
  const pathname = usePathname();
  const [topics, setTopics] = useState<TopicLabel[]>([]);

  useEffect(() => {
    api
      .listPaths()
      .then((rows) => setTopics(rows.map((row) => ({ path_id: row.path_id, name: row.name || row.path_id }))))
      .catch(() => setTopics([]));
  }, [pathname]);

  const navItem = (href: string, label: string, Icon: typeof Compass) => {
    const active = pathname === href || pathname.startsWith(`${href}/`);
    return (
      <Link
        href={href}
        className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] ${
          active ? "bg-accent font-medium" : "hover:bg-accent/60"
        }`}
      >
        <Icon size={15} />
        {label}
      </Link>
    );
  };

  return (
    <nav
      aria-label={t("nav.mastery")}
      className="flex h-full w-[240px] shrink-0 flex-col border-r border-border bg-card/40 px-2.5 py-4"
    >
      <div className="px-2 pb-3 text-sm font-semibold">{t("app.name")}</div>
      <div className="space-y-0.5">
        {navItem(MASTERY_HOME, t("nav.mastery"), Compass)}
        {navItem(settingsRoute("general"), t("nav.settings"), SettingsIcon)}
      </div>

      <div className="mt-6 px-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {t("nav.mastery")}
      </div>
      <div className="mt-1.5 min-h-0 flex-1 space-y-0.5 overflow-y-auto">
        {topics.length === 0 ? (
          <p className="px-2.5 py-2 text-[12px] text-muted-foreground">{t("sessions.none")}</p>
        ) : (
          topics.map((topic) => (
            <Link
              key={topic.path_id}
              href={masteryTopicRoute(topic.path_id)}
              className={`block truncate rounded-lg px-2.5 py-1.5 text-[12.5px] ${
                pathname.includes(topic.path_id) ? "bg-accent" : "hover:bg-accent/60"
              }`}
            >
              {topic.name}
            </Link>
          ))
        )}
      </div>
    </nav>
  );
}
