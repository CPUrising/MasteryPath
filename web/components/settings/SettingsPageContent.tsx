"use client";

import { useTranslation } from "react-i18next";

import { ModelsWorkspace } from "./ModelsWorkspace";
import { ProvidersWorkspace } from "./ProvidersWorkspace";
import { SettingsOverview } from "./SettingsOverview";

export function SettingsPageContent({ section }: { section: string }) {
  const { t } = useTranslation();
  switch (section) {
    case "connections":
      return <ProvidersWorkspace />;
    case "llm":
      return <ModelsWorkspace page="llm" />;
    case "task-models":
      return <ModelsWorkspace page="task-models" />;
    case "embedding":
      return <ModelsWorkspace page="embedding" />;
    case "general":
      return <SettingsOverview />;
    default:
      return (
        <div>
          <h1 className="text-lg font-semibold">{t("settings.title")}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{section}</p>
        </div>
      );
  }
}
