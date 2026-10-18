"use client";

import "@/lib/i18n";

/** Initializes react-i18next on the client and renders its children. */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
