"use client";

import { useEffect } from "react";

/** A brief "just mastered" celebration overlay. */
export function LevelUpCelebration({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, 2200);
    return () => window.clearTimeout(timer);
  }, [onDone]);
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-6 z-40 flex justify-center"
    >
      <div className="rounded-full border border-primary/30 bg-card px-4 py-2 text-sm font-medium shadow-lg">
        ✦
      </div>
    </div>
  );
}
