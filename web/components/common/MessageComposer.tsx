"use client";

import { useRef, useState } from "react";
import { ArrowUp, Check, ChevronDown, Layers, MessageSquare, Paperclip, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { KnowledgeBase, ModelEntry } from "@/lib/types";

export interface ComposerAttachment {
  name: string;
  text: string;
}

const TEXT_FILE = /\.(txt|md|markdown|csv|json|log)$/i;

/**
 * The one composer used by general chat and by the mastery tutor.
 *
 * Colours come from theme variables only, so the same component reads correctly
 * on the dark chat surface and the light study surface; there is no light/dark
 * fork. `capabilityLabel` unset hides the capability chip (mastery is a fixed
 * capability, not a choice).
 */
export function MessageComposer({
  models,
  modelId,
  onModelChange,
  knowledgeBases,
  kbIds,
  onKbChange,
  streaming,
  onSend,
  placeholder,
  askHint,
  capabilityLabel,
}: {
  models: ModelEntry[];
  modelId: string;
  onModelChange: (id: string) => void;
  knowledgeBases: KnowledgeBase[];
  kbIds: string[];
  onKbChange: (ids: string[]) => void;
  streaming: boolean;
  onSend: (text: string, attachments: ComposerAttachment[]) => void;
  placeholder?: string;
  askHint?: string;
  capabilityLabel?: string;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [kbOpen, setKbOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const activeModel = models.find((model) => model.id === modelId) ?? models[0] ?? null;

  const readFiles = async (files: FileList | null) => {
    if (!files) return;
    const next: ComposerAttachment[] = [];
    for (const file of Array.from(files)) {
      if (!TEXT_FILE.test(file.name)) continue;
      next.push({ name: file.name, text: await file.text() });
    }
    if (next.length) setAttachments((current) => [...current, ...next]);
  };

  const submit = () => {
    const value = text.trim();
    if (!value || streaming) return;
    onSend(value, attachments);
    setText("");
    setAttachments([]);
  };

  const toggleKb = (id: string) =>
    onKbChange(kbIds.includes(id) ? kbIds.filter((item) => item !== id) : [...kbIds, id]);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-5">
      <div className="rounded-3xl border border-border bg-card p-3 shadow-sm">
        {askHint && !text && (
          <p className="px-1.5 pb-1 text-[12px] text-muted-foreground">
            {askHint} <span className="opacity-60">· {t("study.tabHint")}</span>
          </p>
        )}
        <textarea
          rows={2}
          value={text}
          disabled={streaming}
          placeholder={placeholder ?? t("chat.placeholder")}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Tab" && !text && askHint) {
              event.preventDefault();
              setText(askHint);
              return;
            }
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          className="max-h-48 w-full resize-none bg-transparent px-1.5 py-1 text-[14px] text-foreground outline-none placeholder:text-muted-foreground"
        />

        {attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5 px-1.5">
            {attachments.map((item) => (
              <span
                key={item.name}
                className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-[11px] text-foreground"
              >
                {item.name}
                <button
                  type="button"
                  aria-label={t("common.remove")}
                  onClick={() =>
                    setAttachments((current) => current.filter((row) => row.name !== item.name))
                  }
                >
                  <X size={11} />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1.5 px-1">
          {capabilityLabel && (
            <span className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-[13px] text-muted-foreground">
              <MessageSquare size={15} />
              {capabilityLabel}
            </span>
          )}
          <button
            type="button"
            aria-label={t("chat.attach")}
            onClick={() => fileRef.current?.click()}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent"
          >
            <Paperclip size={15} />
          </button>
          <input
            ref={fileRef}
            type="file"
            multiple
            hidden
            onChange={(event) => void readFiles(event.target.files)}
          />

          <div className="relative">
            <button
              type="button"
              aria-label={t("chat.knowledge")}
              aria-expanded={kbOpen}
              onClick={() => setKbOpen((value) => !value)}
              className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-[13px] ${
                kbIds.length ? "text-primary" : "text-muted-foreground hover:bg-accent"
              }`}
            >
              <Layers size={15} />
              {kbIds.length > 0 && <span>{kbIds.length}</span>}
            </button>
            {kbOpen && (
              <div className="absolute bottom-full left-0 z-30 mb-2 w-[min(300px,calc(100vw-40px))] overflow-hidden rounded-xl border border-border bg-popover p-1 shadow-xl">
                {knowledgeBases.length === 0 ? (
                  <p className="px-3 py-3 text-[12px] text-muted-foreground">
                    {t("chat.noKnowledge")}
                  </p>
                ) : (
                  knowledgeBases.map((kb) => {
                    const active = kbIds.includes(kb.id);
                    return (
                      <button
                        key={kb.id}
                        type="button"
                        onClick={() => toggleKb(kb.id)}
                        className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] hover:bg-accent/60"
                      >
                        <span
                          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                            active ? "border-primary bg-primary text-primary-foreground" : "border-border"
                          }`}
                        >
                          {active && <Check size={11} />}
                        </span>
                        <span className="min-w-0 flex-1 truncate">{kb.name}</span>
                        <span className="shrink-0 text-[10px] text-muted-foreground">
                          {kb.status}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <label className="relative inline-flex items-center">
              <select
                aria-label={t("chat.model")}
                value={activeModel?.id ?? ""}
                onChange={(event) => onModelChange(event.target.value)}
                className="max-w-[190px] appearance-none rounded-full bg-foreground px-3 py-1 pr-7 text-[12px] font-medium text-background outline-none"
              >
                {models.length === 0 && <option value="">{t("chat.noModel")}</option>}
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name || model.model}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={12}
                className="pointer-events-none absolute right-2 text-background/60"
              />
            </label>
            <button
              type="button"
              aria-label={t("chat.send")}
              disabled={streaming || !text.trim()}
              onClick={submit}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40"
            >
              <ArrowUp size={17} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
