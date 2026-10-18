"use client";

import type { ReactNode } from "react";

export function Tooltip({
  label,
  children,
  side = "top",
}: {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom" | "right";
}) {
  return (
    <span title={label} data-side={side} className="inline-flex">
      {children}
    </span>
  );
}
