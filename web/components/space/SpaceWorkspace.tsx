"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Database, MessageSquare, Notebook } from "lucide-react";
import { useTranslation } from "react-i18next";

import { LearningShell } from "@/components/learning/LearningShell";
import { api } from "@/lib/api";
import { chatApi } from "@/lib/chat-api";
import { knowledgeApi } from "@/lib/knowledge-api";
import {
  chatSessionRoute,
  knowledgeBaseRoute,
  masteryTopicRoute,
} from "@/lib/learning-routes";
import type { ChatSessionSummary, KnowledgeBase, QuestionEntry } from "@/lib/types";

type Tab = "history" | "knowledge" | "questions";

interface HistoryRow {
  key: string;
  title: string;
  href: string;
  kind: string;
  updated: number;
}

export function SpaceWorkspace() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("history");
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [topics, setTopics] = useState<HistoryRow[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [questions, setQuestions] = useState<QuestionEntry[]>([]);

  const load = useCallback(async () => {
    chatApi.list().then(setSessions).catch(() => setSessions([]));
    knowledgeApi.list().then(setKbs).catch(() => setKbs([]));
    api.allQuestions().then(setQuestions).catch(() => setQuestions([]));
    try {
      const paths = await api.listPaths();
      const rows: HistoryRow[] = [];
      for (const path of paths) {
        const detail = await api
          .listSessions(path.path_id)
          .catch(() => ({ sessions: [] }));
        for (const session of detail.sessions) {
          rows.push({
            key: `m-${session.session_id}`,
            title: session.title || session.session_id,
            href: masteryTopicRoute(path.path_id),
            kind: session.mode,
            updated: session.updated_at,
          });
        }
      }
      setTopics(rows);
    } catch {
      setTopics([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const tabButton = (key: Tab, label: string, Icon: typeof MessageSquare) => (
    <button
      key={key}
      type="button"
      onClick={() => setTab(key)}
      className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-[13px] ${
        tab === key ? "bg-accent font-medium" : "text-muted-foreground hover:bg-accent/50"
      }`}
    >
      <Icon size={14} />
      {label}
    </button>
  );

  return (
    <LearningShell title={t("nav.space")} subtitle={t("space.subtitle")}>
      <nav className="mb-5 flex gap-1">
        {tabButton("history", t("space.tab.history"), MessageSquare)}
        {tabButton("knowledge", t("space.tab.knowledge"), Database)}
        {tabButton("questions", t("space.tab.questions"), Notebook)}
      </nav>

      {tab === "history" && (
        <div className="space-y-6">
          <section>
            <h2 className="mb-2 text-[13px] font-semibold">{t("space.chats")}</h2>
            {sessions.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">{t("space.noChats")}</p>
            ) : (
              <ul className="divide-y divide-border rounded-xl border border-border">
                {sessions.map((session) => (
                  <li key={session.session_id}>
                    <Link
                      href={chatSessionRoute(session.session_id)}
                      className="flex items-center gap-3 px-3 py-2.5 hover:bg-accent/40"
                    >
                      <span className="min-w-0 flex-1 truncate text-[13px]">
                        {session.title || t("chat.newChat")}
                      </span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {t("space.messages", { count: session.message_count })}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section>
            <h2 className="mb-2 text-[13px] font-semibold">{t("space.masterySessions")}</h2>
            {topics.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">{t("space.noChats")}</p>
            ) : (
              <ul className="divide-y divide-border rounded-xl border border-border">
                {topics.map((row) => (
                  <li key={row.key}>
                    <Link
                      href={row.href}
                      className="flex items-center gap-3 px-3 py-2.5 hover:bg-accent/40"
                    >
                      <span className="min-w-0 flex-1 truncate text-[13px]">{row.title}</span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">{row.kind}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {tab === "knowledge" && (
        <section>
          {kbs.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">{t("kb.empty.body")}</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {kbs.map((kb) => (
                <li key={kb.id}>
                  <Link
                    href={knowledgeBaseRoute(kb.id)}
                    className="flex items-center gap-3 px-3 py-2.5 hover:bg-accent/40"
                  >
                    <span className="min-w-0 flex-1 truncate text-[13px]">{kb.name}</span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">
                      {t(`kb.status.${kb.status}`, kb.status)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <Link
            href="/knowledge-bases"
            className="mt-3 inline-block text-[13px] text-primary hover:underline"
          >
            {t("kb.create")}
          </Link>
        </section>
      )}

      {tab === "questions" && (
        <section>
          {questions.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">{t("space.noQuestions")}</p>
          ) : (
            <ul className="space-y-2">
              {questions.map((entry) => (
                <li key={entry.entry_id} className="rounded-xl border border-border p-3.5">
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="rounded bg-muted px-1.5 py-0.5">{entry.question_type}</span>
                    <span>{entry.path_name || entry.path_id}</span>
                    {entry.knowledge_point_name && <span>· {entry.knowledge_point_name}</span>}
                  </div>
                  <p className="mt-2 text-[13px]">{entry.question}</p>
                  <p className="mt-1.5 text-[12px] text-muted-foreground">
                    {t("space.answer")}: {entry.correct_answer || "—"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </LearningShell>
  );
}
