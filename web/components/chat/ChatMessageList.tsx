"use client";

import { useEffect, useRef } from "react";

interface DisplayMessage {
  id: string | number;
  role: "user" | "assistant";
  content: string;
  attachments: { name: string }[];
}

/** Plain message list for the dark chat surface. */
export function ChatMessageList({
  messages,
  streaming,
}: {
  messages: DisplayMessage[];
  streaming: boolean;
}) {
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages, streaming]);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
      {messages.map((message) => (
        <div
          key={`${message.id}-${message.role}`}
          className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
        >
          <div
            className={
              message.role === "user"
                ? "max-w-[85%] whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-[14px] leading-relaxed text-primary-foreground"
                : "max-w-[92%] whitespace-pre-wrap text-[14px] leading-relaxed text-foreground"
            }
          >
            {message.content}
            {message.attachments.length > 0 && (
              <span className="mt-1 block text-[11px] opacity-70">
                {message.attachments.map((item) => item.name).join(", ")}
              </span>
            )}
          </div>
        </div>
      ))}
      <div ref={bottom} />
    </div>
  );
}
