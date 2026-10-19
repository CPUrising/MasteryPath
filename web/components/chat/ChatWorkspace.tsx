"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

import { ChatComposer, type ComposerAttachment } from "./ChatComposer";
import { ChatMessageList } from "./ChatMessageList";
import { WelcomeMark } from "./WelcomeMark";
import { api } from "@/lib/api";
import { chatApi } from "@/lib/chat-api";
import { knowledgeApi } from "@/lib/knowledge-api";
import { chatSessionRoute } from "@/lib/learning-routes";
import type { ChatSessionSummary, KnowledgeBase, ModelEntry, ModelSection } from "@/lib/types";

interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments: { name: string }[];
}

function greetingKey(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return "chat.greeting.morning";
  if (hour < 18) return "chat.greeting.afternoon";
  return "chat.greeting.evening";
}

export function ChatWorkspace({ sessionId }: { sessionId?: string }) {
  const { t } = useTranslation();
  const router = useRouter();
  const [session, setSession] = useState<ChatSessionSummary | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [modelId, setModelId] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [kbIds, setKbIds] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [greeting] = useState(() => greetingKey(new Date()));

  const refreshSessions = useCallback(async () => {
    try {
      await chatApi.list();
    } catch {
      /* the sidebar refreshes on navigation */
    }
  }, []);

  useEffect(() => {
    api
      .getSettings("llm")
      .then((value) => {
        const section = value as ModelSection;
        setModels(section.models ?? []);
        setModelId(section.active_id || section.models?.[0]?.id || "");
      })
      .catch(() => setModels([]));
    knowledgeApi.list().then(setKnowledgeBases).catch(() => setKnowledgeBases([]));
  }, []);

  useEffect(() => {
    if (!sessionId) {
      setSession(null);
      setMessages([]);
      return;
    }
    chatApi
      .get(sessionId)
      .then((detail) => {
        setSession(detail.session);
        setModelId(detail.session.model_id || modelId);
        setKbIds(detail.session.kb_ids || []);
        setMessages(
          detail.messages.map((message) => ({
            id: `m-${message.id}`,
            role: message.role,
            content: message.content,
            attachments: message.attachments ?? [],
          })),
        );
      })
      .catch(() => setError(t("chat.loadFailed")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const changeModel = (next: string) => {
    setModelId(next);
    if (session) void chatApi.update(session.session_id, { model_id: next }).catch(() => undefined);
  };

  const changeKb = (next: string[]) => {
    setKbIds(next);
    if (session) void chatApi.update(session.session_id, { kb_ids: next }).catch(() => undefined);
  };

  const send = async (text: string, attachments: ComposerAttachment[]) => {
    setError("");
    setStreaming(true);
    const userMessage: LocalMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      attachments: attachments.map((item) => ({ name: item.name })),
    };
    const assistantMessage: LocalMessage = {
      id: `a-${Date.now()}`,
      role: "assistant",
      content: "",
      attachments: [],
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    try {
      let active = session;
      if (!active) {
        active = await chatApi.create({ model_id: modelId, kb_ids: kbIds });
        setSession(active);
        router.replace(chatSessionRoute(active.session_id));
      }
      const sid = active.session_id;
      await chatApi.streamTurn(
        sid,
        text,
        attachments.map((item) => ({ name: item.name, text: item.text })),
        (event) => {
          if (event.type === "delta" && event.text) {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessage.id
                  ? { ...message, content: message.content + event.text }
                  : message,
              ),
            );
          } else if (event.type === "error") {
            setError(event.message || t("chat.sendFailed"));
            setMessages((current) => current.filter((message) => message.id !== assistantMessage.id));
          } else if (event.type === "done" && event.title) {
            setSession((current) => (current ? { ...current, title: event.title! } : current));
          }
        },
      );
      void refreshSessions();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("chat.sendFailed"));
      setMessages((current) => current.filter((message) => message.id !== assistantMessage.id));
    } finally {
      setStreaming(false);
    }
  };

  const title = useMemo(() => session?.title || t("chat.newChat"), [session, t]);
  const activeModelName = useMemo(() => {
    const entry = models.find((model) => model.id === modelId) ?? models[0];
    return entry ? entry.name || entry.model : "";
  }, [models, modelId]);

  return (
    <div className="dark flex h-full flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-5">
        <h1 className="min-w-0 flex-1 truncate text-[14px] font-medium">{title}</h1>
        {activeModelName && (
          <span className="truncate text-[12px] text-muted-foreground">{activeModelName}</span>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
            <WelcomeMark />
            <p className="text-xl font-medium tracking-tight">{t(greeting)}</p>
          </div>
        ) : (
          <ChatMessageList messages={messages} streaming={streaming} />
        )}
      </div>

      {error && (
        <p role="alert" className="mx-auto w-full max-w-3xl px-4 pb-2 text-[12px] text-destructive">
          {error}
        </p>
      )}

      <ChatComposer
        models={models}
        modelId={modelId}
        onModelChange={changeModel}
        knowledgeBases={knowledgeBases}
        kbIds={kbIds}
        onKbChange={changeKb}
        streaming={streaming}
        onSend={(text, attachments) => void send(text, attachments)}
      />
    </div>
  );
}
