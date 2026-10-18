"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Field, SettingsPageHeader, SettingsSection } from "./shared";
import { api } from "@/lib/api";
import { currentLanguage, setLanguage } from "@/lib/i18n";

interface GeneralSettings {
  interface_language: string;
  response_language: string;
}

export function SettingsOverview() {
  const { t } = useTranslation();
  const [value, setValue] = useState<GeneralSettings>({ interface_language: currentLanguage(), response_language: "zh" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings("general").then((data) => setValue(data as GeneralSettings)).catch(() => undefined);
  }, []);

  return (
    <div>
      <SettingsPageHeader title={t("settings.general.title")} description={t("settings.general.desc")} />
      <SettingsSection title={t("settings.general.title")}>
        <Field label="Interface language">
          <select
            value={value.interface_language}
            onChange={(event) => {
              const lang = event.target.value as "zh" | "en";
              setValue({ ...value, interface_language: lang });
              setLanguage(lang);
            }}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </Field>
        <Field label="Response language">
          <select
            value={value.response_language}
            onChange={(event) => setValue({ ...value, response_language: event.target.value })}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </Field>
        <button
          type="button"
          onClick={async () => {
            await api.putSettings("general", value);
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
