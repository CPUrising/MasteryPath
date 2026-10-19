"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Field, SettingsPageHeader, SettingsSection } from "./shared";
import { api } from "@/lib/api";

const CHUNK_SIZES = [512, 800, 1024, 1536];
const CHUNK_OVERLAPS = [0, 64, 100, 128, 200];

interface IndexingSettingsValue {
  chunk_size: number;
  chunk_overlap: number;
}

export function IndexingSettings() {
  const { t } = useTranslation();
  const [value, setValue] = useState<IndexingSettingsValue>({
    chunk_size: 512,
    chunk_overlap: 64,
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getSettings("indexing")
      .then((data) => setValue(data as IndexingSettingsValue))
      .catch(() => undefined);
  }, []);

  const invalid = value.chunk_overlap >= value.chunk_size;

  return (
    <div>
      <SettingsPageHeader
        title={t("settings.indexing.title")}
        description={t("settings.indexing.desc")}
      />
      <SettingsSection title={t("settings.indexing.title")}>
        <Field label={t("kb.chunkSize")}>
          <select
            value={value.chunk_size}
            onChange={(event) =>
              setValue({ ...value, chunk_size: Number(event.target.value) })
            }
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            {CHUNK_SIZES.map((size) => (
              <option key={size} value={size}>
                {size} {t("kb.tokens")}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("kb.chunkOverlap")}>
          <select
            value={value.chunk_overlap}
            onChange={(event) =>
              setValue({ ...value, chunk_overlap: Number(event.target.value) })
            }
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            {CHUNK_OVERLAPS.map((overlap) => (
              <option key={overlap} value={overlap}>
                {overlap} {t("kb.tokens")}
              </option>
            ))}
          </select>
        </Field>
        <p className="text-[12px] text-muted-foreground">{t("settings.indexing.hint")}</p>
        {invalid && <p className="text-[12px] text-destructive">{t("kb.chunkInvalid")}</p>}
        {error && <p className="text-[12px] text-destructive">{error}</p>}
        <button
          type="button"
          disabled={invalid}
          onClick={async () => {
            try {
              await api.putSettings("indexing", value);
              setSaved(true);
              setError("");
              window.setTimeout(() => setSaved(false), 1500);
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : String(reason));
            }
          }}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        >
          {saved ? t("settings.saved") : t("settings.save")}
        </button>
      </SettingsSection>
    </div>
  );
}
