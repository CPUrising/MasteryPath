"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Field, SettingsPageHeader, SettingsSection, TextInput } from "./shared";
import { api } from "@/lib/api";

interface EmbeddingSelection {
  provider: string;
  model: string;
  dimension: number;
}

export function EmbeddingSettings() {
  const { t } = useTranslation();
  const [value, setValue] = useState<EmbeddingSelection>({ provider: "", model: "", dimension: 0 });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings("embedding").then((data) => setValue(data as EmbeddingSelection)).catch(() => undefined);
  }, []);

  return (
    <div>
      <SettingsPageHeader title={t("settings.embedding.title")} description={t("settings.embedding.desc")} />
      <SettingsSection title={t("settings.embedding.title")}>
        <Field label={t("settings.provider")}>
          <TextInput value={value.provider} onChange={(provider) => setValue({ ...value, provider })} />
        </Field>
        <Field label={t("settings.model")}>
          <TextInput value={value.model} onChange={(model) => setValue({ ...value, model })} />
        </Field>
        <Field label="dimension">
          <TextInput
            value={String(value.dimension)}
            onChange={(dimension) => setValue({ ...value, dimension: Number(dimension) || 0 })}
          />
        </Field>
        <button
          type="button"
          onClick={async () => {
            await api.putSettings("embedding", value);
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
