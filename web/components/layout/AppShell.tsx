"use client";

import { useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import { useTranslation } from "react-i18next";

/** The app frame: sidebar + content; a drawer under md. */
export default function AppShell({
  sidebar,
  children,
}: {
  sidebar: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  return (
    <div className="flex h-dvh overflow-hidden">
      {drawerOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 md:hidden" aria-hidden onClick={() => setDrawerOpen(false)} />
      )}
      <div
        className={`max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:transition-transform ${
          drawerOpen ? "max-md:translate-x-0" : "max-md:-translate-x-full"
        }`}
      >
        {sidebar}
      </div>
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
        <div className="flex h-11 shrink-0 items-center gap-2 border-b border-border px-2 md:hidden">
          <button
            type="button"
            aria-label={t("nav.mastery")}
            onClick={() => setDrawerOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/50"
          >
            <Menu size={18} />
          </button>
          <span className="font-semibold">{t("app.name")}</span>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
      </main>
    </div>
  );
}
