"use client";

import { useTranslation } from "react-i18next";

import { EmbeddingSettings } from "./EmbeddingSettings";
import { ModelsWorkspace, TaskModelsWorkspace } from "./ModelsWorkspace";
import { ProvidersWorkspace } from "./ProvidersWorkspace";
import { SettingsOverview } from "./SettingsOverview";

export function SettingsPageContent({ section }: { section: string }) {
  const { t } = useTranslation();
  switch (section) {
    case "connections":
      return <ProvidersWorkspace />;
    case "llm":
      return <ModelsWorkspace />;
    case "task-models":
      return <TaskModelsWorkspace />;
    case "embedding":
      return <EmbeddingSettings />;
    case "general":
      return <SettingsOverview />;
    default:
      return (
        <div className="p-6">
          <h1 className="text-lg font-semibold">{t("settings.title")}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{section}</p>
        </div>
      );
  }
}
