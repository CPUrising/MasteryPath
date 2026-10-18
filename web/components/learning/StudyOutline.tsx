"use client";

import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MapEntry } from "@/lib/types";

function markClass(status: string, current: boolean): string {
  if (status === "mastered") return "mastery-dot-mastered";
  if (current) return "mastery-dot-current";
  if (status === "learning") return "mastery-dot-learning";
  return "mastery-dot-new";
}

/** The study screen's outline rail — same information, peripheral weight. */
export function StudyOutline({
  map,
  currentPointId,
  justMasteredId,
  collapsed,
  onToggleCollapsed,
}: {
  map: Record<string, MapEntry>;
  currentPointId: string;
  justMasteredId?: string | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const { t } = useTranslation();
  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label={t("dash.outline")}
        className="flex h-full w-full flex-col items-center gap-2 pt-4 text-muted-foreground hover:bg-muted/50"
      >
        <ChevronsRight className="h-4 w-4" />
        <span className="text-[10px] uppercase tracking-widest" style={{ writingMode: "vertical-rl" }}>
          {t("dash.outline")}
        </span>
      </button>
    );
  }

  const byModule = new Map<string, { name: string; entries: [string, MapEntry][] }>();
  for (const [kpId, entry] of Object.entries(map)) {
    const bucket = byModule.get(entry.module_id) ?? { name: entry.module_name, entries: [] };
    bucket.entries.push([kpId, entry]);
    byModule.set(entry.module_id, bucket);
  }
  const mastered = Object.values(map).filter((entry) => entry.status === "mastered").length;

  return (
    <nav aria-label={t("dash.outline")} className="pb-10">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/70">
          {t("dash.outline")}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[10.5px] tabular-nums text-muted-foreground/60">
            {mastered}/{Object.keys(map).length}
          </span>
          <button type="button" onClick={onToggleCollapsed} aria-label={t("dash.outline")} className="text-muted-foreground/60">
            <ChevronsLeft className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="mt-5 space-y-6">
        {[...byModule.entries()].map(([moduleId, bucket]) => (
          <section key={moduleId}>
            <h2 className="mb-1.5 text-[12.5px] font-semibold">{bucket.name}</h2>
            <ul className="relative space-y-0.5 before:absolute before:bottom-3 before:left-[8px] before:top-3 before:w-px before:bg-border">
              {bucket.entries.map(([kpId, entry]) => {
                const current = kpId === currentPointId;
                const just = kpId === justMasteredId;
                return (
                  <li
                    key={kpId}
                    className={`flex items-center gap-2 rounded-md py-1 pl-1 ${
                      just ? "mastery-just-mastered-row" : current ? "bg-primary/5" : ""
                    }`}
                  >
                    <span className="relative z-[1] flex h-4 w-4 items-center justify-center">
                      <span
                        aria-hidden
                        className={`h-[8px] w-[8px] rounded-full ${markClass(entry.status, current)} ${
                          just ? "mastery-just-mastered-dot" : ""
                        }`}
                      />
                    </span>
                    <span
                      className={`min-w-0 text-[12px] ${
                        current || just ? "font-medium" : entry.status === "mastered" ? "text-muted-foreground/75" : "text-muted-foreground"
                      }`}
                    >
                      {entry.name}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </nav>
  );
}
