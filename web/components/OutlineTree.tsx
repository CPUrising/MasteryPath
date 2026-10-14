"use client";

import type { MapEntry } from "../lib/types";

const STATUS_COLOR: Record<string, string> = {
  new: "#9ca3af",
  learning: "#f59e0b",
  mastered: "#10b981",
};

export function OutlineTree({
  map,
  onOverride,
}: {
  map: Record<string, MapEntry>;
  onOverride?: (kpId: string) => void;
}) {
  const byModule = new Map<string, { moduleName: string; entries: [string, MapEntry][] }>();
  for (const [kpId, entry] of Object.entries(map)) {
    const bucket = byModule.get(entry.module_id) ?? { moduleName: entry.module_name, entries: [] };
    bucket.entries.push([kpId, entry]);
    byModule.set(entry.module_id, bucket);
  }

  return (
    <div>
      {[...byModule.values()].map((bucket) => (
        <section key={bucket.moduleName} style={{ marginBottom: 12 }}>
          <h4 style={{ margin: "0 0 6px", fontSize: 13, color: "#6b7280" }}>
            {bucket.moduleName}
          </h4>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {bucket.entries.map(([kpId, entry]) => (
              <li
                key={kpId}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "4px 0",
                  opacity: entry.status === "mastered" ? 0.6 : 1,
                }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: STATUS_COLOR[entry.status] ?? "#9ca3af",
                  }}
                />
                <span style={{ flex: 1 }}>{entry.name}</span>
                <code style={{ fontSize: 11, color: "#6b7280" }}>{entry.type}</code>
                {entry.grounding === "ungrounded" && (
                  <span title="待补充来源" style={{ fontSize: 11, color: "#ef4444" }}>
                    待补来源
                  </span>
                )}
                {onOverride && entry.status !== "mastered" && (
                  <button onClick={() => onOverride(kpId)} style={{ fontSize: 11 }}>
                    声明掌握
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
