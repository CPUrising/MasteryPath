"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SettingsNav } from "./SettingsNav";
import { MASTERY_HOME } from "@/lib/learning-routes";

/** Settings owns its navigation and a way back to the app (DeepTutor parity). */
export function SettingsShell({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 flex h-dvh overflow-hidden bg-background">
      <aside className="hidden w-[248px] shrink-0 flex-col border-r border-border bg-muted/25 md:flex">
        <div className="px-2.5 pb-1.5 pt-4">
          <Link
            href={MASTERY_HOME}
            className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] font-medium outline-none transition hover:bg-accent/60"
          >
            <ArrowLeft size={16} strokeWidth={1.7} />
            {t("settings.backToApp")}
          </Link>
        </div>
        <SettingsNav />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex h-14 shrink-0 items-center border-b border-border px-3 md:hidden">
          <Link href={MASTERY_HOME} className="flex items-center gap-2 text-[13px] font-medium">
            <ArrowLeft size={16} strokeWidth={1.7} />
            {t("settings.backToApp")}
          </Link>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-4xl px-6 py-7">{children}</div>
        </div>
      </main>
    </div>
  );
}
