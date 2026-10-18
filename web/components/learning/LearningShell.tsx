"use client";

import type { ReactNode } from "react";

/** Shared page rhythm for the mastery surfaces. */
export function LearningShell({
  title,
  subtitle,
  action,
  children,
}: {
  title: ReactNode;
  subtitle: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        </div>
        {action}
      </header>
      <div className="mt-6">{children}</div>
    </div>
  );
}
