"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Field, SettingsPageHeader, SettingsSection, TextInput } from "./shared";
import { api } from "@/lib/api";
import type { Provider } from "@/lib/types";

interface ModelSelection {
  provider_id: string;
  model: string;
}

function ModelWorkspace({ section, titleKey, descKey }: { section: string; titleKey: string; descKey: string }) {
  const { t } = useTranslation();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selection, setSelection] = useState<ModelSelection>({ provider_id: "", model: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getProviders().then(setProviders).catch(() => setProviders([]));
    api.getSettings(section).then((value) => setSelection(value as ModelSelection)).catch(() => undefined);
  }, [section]);

  return (
    <div>
      <SettingsPageHeader title={t(titleKey)} description={t(descKey)} />
      <SettingsSection title={t(titleKey)}>
        <Field label={t("settings.provider")}>
          <select
            value={selection.provider_id}
            onChange={(event) => setSelection({ ...selection, provider_id: event.target.value })}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">—</option>
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name || provider.id}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("settings.model")}>
          <TextInput value={selection.model} onChange={(value) => setSelection({ ...selection, model: value })} />
        </Field>
        <button
          type="button"
          onClick={async () => {
            await api.putSettings(section, selection);
            setSaved(true);
            window.setTimeout(() => setSaved(false), 1500);
          }}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground"
        >
          {saved ? t("settings.saved") : t("settings.save")}
        </button>
      </SettingsSection>
    </div>
  );
}

export function ModelsWorkspace() {
  return <ModelWorkspace section="llm" titleKey="settings.llm.title" descKey="settings.llm.desc" />;
}

export function TaskModelsWorkspace() {
  return <ModelWorkspace section="task-models" titleKey="settings.task.title" descKey="settings.task.desc" />;
}
