"use client";

import type { TurnEvent } from "../lib/types";

export function ActivityDrawer({
  events,
  open,
  onToggle,
}: {
  events: TurnEvent[];
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{ borderLeft: "1px solid #e5e7eb", paddingLeft: 12, minWidth: 220 }}>
      <button onClick={onToggle} style={{ marginBottom: 8 }}>
        {open ? "收起 Activity" : "展开 Activity"}
      </button>
      {open && (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 12 }}>
          {events.map((event, index) => (
            <li key={index} style={{ marginBottom: 6 }}>
              <code style={{ color: "#6b7280" }}>{event.type}</code>
              {typeof event.data.name === "string" && <span> · {event.data.name}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
