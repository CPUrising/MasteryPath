"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  Database,
  Library,
  MessageSquare,
  Plus,
  Settings as SettingsIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/lib/api";
import { chatApi } from "@/lib/chat-api";
import {
  CHAT_HOME,
  KNOWLEDGE_HOME,
  MASTERY_HOME,
  SPACE_HOME,
  chatSessionRoute,
  masteryTopicRoute,
  settingsRoute,
} from "@/lib/learning-routes";
import type { ChatSessionSummary } from "@/lib/types";

interface TopicLabel {
  path_id: string;
  name: string;
}

export function WorkspaceSidebar() {
  const { t } = useTranslation();
  const pathname = usePathname();
  const [topics, setTopics] = useState<TopicLabel[]>([]);
  const [chats, setChats] = useState<ChatSessionSummary[]>([]);

  useEffect(() => {
    api
      .listPaths()
      .then((rows) =>
        setTopics(rows.map((row) => ({ path_id: row.path_id, name: row.name || row.path_id }))),
      )
      .catch(() => setTopics([]));
    chatApi
      .list()
      .then((rows) => setChats(rows.slice(0, 10)))
      .catch(() => setChats([]));
  }, [pathname]);

  const navItem = (href: string, label: string, Icon: typeof Compass) => {
    const active =
      href === CHAT_HOME
        ? pathname === CHAT_HOME || pathname.startsWith(`${CHAT_HOME}/`)
        : pathname === href || pathname.startsWith(`${href}/`);
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
      aria-label={t("app.name")}
      className="flex h-full w-[240px] shrink-0 flex-col border-r border-border bg-card/40 px-2.5 py-4"
    >
      <div className="px-2 pb-3 text-sm font-semibold">{t("app.name")}</div>
      <div className="space-y-0.5">
        {navItem(CHAT_HOME, t("nav.chat"), MessageSquare)}
        {navItem(KNOWLEDGE_HOME, t("nav.knowledge"), Database)}
        {navItem(SPACE_HOME, t("nav.space"), Library)}
        {navItem(MASTERY_HOME, t("nav.mastery"), Compass)}
      </div>

      <div className="mt-6 flex items-center justify-between px-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {t("nav.recent")}
        </span>
        <Link
          href={CHAT_HOME}
          aria-label={t("chat.newChat")}
          className="text-muted-foreground hover:text-foreground"
        >
          <Plus size={13} />
        </Link>
      </div>
      <div className="mt-1.5 max-h-[38%] min-h-0 space-y-0.5 overflow-y-auto">
        {chats.length === 0 ? (
          <p className="px-2.5 py-2 text-[12px] text-muted-foreground">{t("nav.noRecent")}</p>
        ) : (
          chats.map((chat) => (
            <Link
              key={chat.session_id}
              href={chatSessionRoute(chat.session_id)}
              className={`block truncate rounded-lg px-2.5 py-1.5 text-[12.5px] ${
                pathname.includes(chat.session_id) ? "bg-accent" : "hover:bg-accent/60"
              }`}
            >
              {chat.title || t("chat.newChat")}
            </Link>
          ))
        )}
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

      <div className="mt-2 border-t border-border pt-2">
        {navItem(settingsRoute("general"), t("nav.settings"), SettingsIcon)}
      </div>
    </nav>
  );
}
