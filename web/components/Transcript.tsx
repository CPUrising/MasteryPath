"use client";

import type { PendingQuestion } from "../lib/types";

export interface TranscriptItem {
  role: "user" | "tutor";
  text: string;
  card?: PendingQuestion;
}

export function Transcript({
  items,
  onAnswer,
}: {
  items: TranscriptItem[];
  onAnswer: (label: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((item, index) => (
        <div
          key={index}
          style={{
            alignSelf: item.role === "user" ? "flex-end" : "flex-start",
            maxWidth: "80%",
            background: item.role === "user" ? "#dbeafe" : "#f3f4f6",
            borderRadius: 12,
            padding: "8px 12px",
            whiteSpace: "pre-wrap",
          }}
        >
          <div>{item.text}</div>
          {item.card && (
            <div style={{ marginTop: 8 }}>
              <strong>{item.card.prompt}</strong>
              {item.card.options.length > 0 && (
                <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0" }}>
                  {item.card.options.map((option) => (
                    <li key={option.label} style={{ margin: "4px 0" }}>
                      <button onClick={() => onAnswer(option.label)}>
                        {option.label}. {option.body}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
