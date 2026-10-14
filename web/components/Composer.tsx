"use client";

import { useState } from "react";

export function Composer({
  suggestion,
  onSend,
  disabled,
}: {
  suggestion: string;
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");

  return (
    <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: 8 }}>
      {suggestion && !text && (
        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
          建议：{suggestion} <span style={{ color: "#9ca3af" }}>（按 Tab 采纳）</span>
        </div>
      )}
      <textarea
        value={text}
        placeholder="输入消息…（Tab 采纳建议，Enter 发送，Shift+Enter 换行）"
        disabled={disabled}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Tab" && !text && suggestion) {
            event.preventDefault();
            setText(suggestion);
            return;
          }
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            const value = text.trim();
            if (!value) return;
            onSend(value);
            setText("");
          }
        }}
        rows={3}
        style={{ width: "100%", resize: "vertical", font: "inherit", padding: 8 }}
      />
    </div>
  );
}
