"use client";

import type { PathState } from "../lib/types";

export function SideViewer({
  state,
  onResolveGap,
}: {
  state: PathState;
  onResolveGap: (gapId: string, action: "accept" | "regenerate") => void;
}) {
  return (
    <aside style={{ borderLeft: "1px solid #e5e7eb", paddingLeft: 12, minWidth: 240 }}>
      <h3 style={{ fontSize: 14, marginTop: 0 }}>侧边查看器</h3>
      <p style={{ fontSize: 12, color: "#6b7280" }}>
        引用、生成材料与缺口处理。原始目标：{state.goal || "（未填写）"}
      </p>
      {state.gaps.length > 0 && (
        <section>
          <h4 style={{ fontSize: 13 }}>来源缺口</h4>
          <ul style={{ listStyle: "none", padding: 0, fontSize: 12 }}>
            {state.gaps.map((gap) => (
              <li key={gap.id} style={{ marginBottom: 6 }}>
                <code>{gap.kind}</code> · {gap.ref}
                {gap.resolution ? (
                  <em>（已处理：{gap.resolution}）</em>
                ) : (
                  <span>
                    {" "}
                    <button onClick={() => onResolveGap(gap.id, "accept")}>接受</button>{" "}
                    <button onClick={() => onResolveGap(gap.id, "regenerate")}>重生成</button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}
