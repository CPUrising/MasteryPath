"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Field, SettingsPageHeader, SettingsSection, TextInput } from "./shared";
import { api } from "@/lib/api";
import type { Provider } from "@/lib/types";

export function ProvidersWorkspace() {
  const { t } = useTranslation();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getProviders().then(setProviders).catch(() => setProviders([]));
  }, []);

  const update = (index: number, patch: Partial<Provider>) =>
    setProviders((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  return (
    <div>
      <SettingsPageHeader title={t("settings.conn.title")} description={t("settings.conn.desc")} />
      <SettingsSection title={t("settings.conn.title")}>
        {providers.map((provider, index) => (
          <div key={index} className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-3">
            <Field label={t("settings.provider.name")}>
              <TextInput value={provider.name} onChange={(value) => update(index, { name: value })} />
            </Field>
            <Field label={t("settings.provider.url")}>
              <TextInput value={provider.base_url} onChange={(value) => update(index, { base_url: value })} />
            </Field>
            <Field label={t("settings.provider.key")}>
              <TextInput type="password" value={provider.api_key} onChange={(value) => update(index, { api_key: value })} />
            </Field>
            <button
              type="button"
              onClick={() => setProviders((rows) => rows.filter((_, i) => i !== index))}
              className="justify-self-start text-[12px] text-destructive hover:underline"
            >
              {t("common.remove")}
            </button>
          </div>
        ))}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() =>
              setProviders((rows) => [...rows, { id: `p${rows.length + 1}`, name: "", base_url: "", api_key: "" }])
            }
            className="h-9 rounded-lg border border-border px-3.5 text-[13px]"
          >
            {t("settings.addProvider")}
          </button>
          <button
            type="button"
            onClick={async () => {
              await api.putSettings("providers", providers);
              setSaved(true);
              window.setTimeout(() => setSaved(false), 1500);
            }}
            className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground"
          >
            {saved ? t("settings.saved") : t("settings.save")}
          </button>
        </div>
      </SettingsSection>
    </div>
  );
}
