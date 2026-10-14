"use client";

import type { Mode } from "../lib/types";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "outline", label: "大纲", hint: "只能改地图" },
  { id: "study", label: "学习", hint: "能讲能考" },
  { id: "review", label: "复习", hint: "只考已掌握" },
];

export function ModeBar({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 8 }} role="tablist" aria-label="学习模式">
      {MODES.map((item) => (
        <button
          key={item.id}
          role="tab"
          aria-selected={mode === item.id}
          title={item.hint}
          onClick={() => onChange(item.id)}
          style={{
            padding: "6px 14px",
            borderRadius: 999,
            border: "1px solid #d1d5db",
            background: mode === item.id ? "#3b82f6" : "#fff",
            color: mode === item.id ? "#fff" : "#374151",
            cursor: "pointer",
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
