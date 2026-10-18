"use client";

import { useTranslation } from "react-i18next";

import type { MapEntry } from "@/lib/types";

function dotClass(status: string): string {
  if (status === "mastered") return "mastery-dot-mastered";
  if (status === "learning") return "mastery-dot-learning";
  return "mastery-dot-new";
}

export function ModuleOutline({
  map,
  onOverride,
}: {
  map: Record<string, MapEntry>;
  onOverride?: (kpId: string) => void;
}) {
  const { t } = useTranslation();
  const byModule = new Map<string, { name: string; entries: [string, MapEntry][] }>();
  for (const [kpId, entry] of Object.entries(map)) {
    const bucket = byModule.get(entry.module_id) ?? { name: entry.module_name, entries: [] };
    bucket.entries.push([kpId, entry]);
    byModule.set(entry.module_id, bucket);
  }
  return (
    <div className="space-y-6">
      {[...byModule.values()].map((bucket) => (
        <section key={bucket.name}>
          <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
            {bucket.name}
          </h3>
          <ul className="space-y-1">
            {bucket.entries.map(([kpId, entry]) => (
              <li key={kpId} className="flex items-center gap-2.5 rounded-md px-2 py-1.5 hover:bg-muted/50">
                <span aria-hidden className={`h-[9px] w-[9px] shrink-0 rounded-full ${dotClass(entry.status)}`} />
                <span className={`flex-1 text-[13px] ${entry.status === "mastered" ? "text-muted-foreground" : ""}`}>
                  {entry.name}
                </span>
                <code className="text-[11px] text-muted-foreground">{entry.type}</code>
                {entry.grounding === "ungrounded" && (
                  <span title="待补充来源" className="text-[11px] text-destructive">
                    {t("dash.sources")}
                  </span>
                )}
                {onOverride && entry.status !== "mastered" && (
                  <button
                    type="button"
                    onClick={() => onOverride(kpId)}
                    className="text-[11px] text-primary hover:underline"
                  >
                    {t("dash.next")}
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
