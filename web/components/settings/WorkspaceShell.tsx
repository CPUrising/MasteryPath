"use client";

import { Search } from "lucide-react";
import type { ReactNode } from "react";

const CARD_BASE =
  "group relative w-full rounded-xl border px-4 py-3 text-left outline-none transition";

/** Row in a workspace rail. `active` is the row being edited. */
export function workspaceCardClass(active: boolean): string {
  return `${CARD_BASE} ${
    active
      ? "border-primary/60 bg-primary/5 ring-1 ring-primary/20"
      : "border-border hover:border-foreground/20 hover:bg-accent/60"
  }`;
}

/** Master–detail split: a list rail that stays put while the editor scrolls. */
export function WorkspaceSplit({ rail, detail }: { rail: ReactNode; detail: ReactNode }) {
  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,280px)_minmax(0,1fr)] xl:gap-6">
      {rail}
      {detail}
    </div>
  );
}

export function WorkspaceRail({
  action,
  search,
  children,
  empty,
}: {
  action?: ReactNode;
  search: { label: string; value: string; onChange: (value: string) => void; placeholder: string };
  children: ReactNode;
  empty?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2.5">
      {action}
      <div className="relative">
        <Search size={14} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          aria-label={search.label}
          value={search.value}
          onChange={(event) => search.onChange(event.target.value)}
          placeholder={search.placeholder}
          className="min-h-10 w-full rounded-lg border border-border bg-transparent py-2.5 pl-8 pr-3 text-[13px] outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
        />
      </div>
      {empty ? (
        <div className="rounded-xl border border-dashed border-border px-4 py-6 text-[13px] leading-relaxed text-muted-foreground">
          {empty}
        </div>
      ) : (
        <div className="flex max-h-[26rem] min-h-0 flex-col gap-2 overflow-y-auto overscroll-contain xl:max-h-[calc(100dvh-14rem)]">
          {children}
        </div>
      )}
    </div>
  );
}

/** Placeholder for the detail pane before anything is picked. */
export function WorkspaceDetailEmpty({
  icon,
  title,
  hint,
}: {
  icon: ReactNode;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex min-h-[18rem] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border px-8 py-12 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {icon}
      </span>
      <p className="text-[13.5px] font-medium">{title}</p>
      {hint && <p className="max-w-[38ch] text-[12.5px] leading-relaxed text-muted-foreground">{hint}</p>}
    </div>
  );
}
