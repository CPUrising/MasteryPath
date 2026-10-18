"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { PROVIDER_CATALOG, type CatalogProvider } from "./ProviderCatalog";
import { TextInput } from "./shared";

export interface NewProviderInput {
  name: string;
  base_url: string;
  requires_key: boolean;
}

/** Add a provider by picking a card, like DeepTutor's Add provider panel. */
export function AddProviderPanel({
  onCancel,
  onCreate,
}: {
  onCancel: () => void;
  onCreate: (input: NewProviderInput) => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<string>("");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");

  const options = useMemo(
    () =>
      PROVIDER_CATALOG.filter((provider) =>
        `${provider.name} ${provider.id}`.toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [query],
  );
  const selected: CatalogProvider | undefined = PROVIDER_CATALOG.find((p) => p.id === picked);
  const custom = picked === "custom";

  const submit = () => {
    if (!selected) return;
    onCreate({
      name: custom ? name.trim() : selected.name,
      base_url: custom ? url.trim() : selected.base_url,
      requires_key: selected.requires_key,
    });
  };

  return (
    <section className="min-w-0 space-y-4 rounded-2xl border border-border bg-card p-5">
      <h3 className="text-base font-semibold">{t("settings.addProvider")}</h3>
      <input
        type="search"
        value={query}
        aria-label={t("settings.findProvider")}
        placeholder={t("settings.findProvider")}
        onChange={(event) => setQuery(event.target.value)}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-[13px] outline-none focus:ring-2 focus:ring-ring/30"
      />
      <div role="radiogroup" aria-label={t("settings.provider")} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((provider) => (
          <button
            key={provider.id}
            type="button"
            role="radio"
            aria-checked={picked === provider.id}
            onClick={() => {
              setPicked(provider.id);
              if (provider.id !== "custom") {
                setName(provider.name);
                setUrl(provider.base_url);
              }
            }}
            className={`flex min-h-20 flex-col gap-2 rounded-xl border p-3.5 text-left transition ${
              picked === provider.id ? "border-primary bg-accent" : "border-border hover:bg-accent/60"
            }`}
          >
            <span className="flex items-center gap-2.5 text-[14px] font-medium">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-muted text-[10px] font-semibold text-muted-foreground">
                {provider.monogram}
              </span>
              {provider.id === "custom" ? t("settings.customProvider") : provider.name}
            </span>
            <span className="text-[11px] text-muted-foreground">
              {provider.requires_key ? t("settings.provider.key") : t("settings.noKeyNeeded")}
            </span>
          </button>
        ))}
      </div>
      {custom && (
        <div className="grid gap-3 rounded-xl border border-border bg-background p-4 sm:grid-cols-2">
          <TextInput value={name} onChange={setName} />
          <TextInput value={url} onChange={setUrl} />
        </div>
      )}
      <div className="flex gap-2 border-t border-border pt-4">
        <button
          type="button"
          disabled={!selected || (custom && (!name.trim() || !url.trim()))}
          onClick={submit}
          className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("settings.continue")}
        </button>
        <button type="button" onClick={onCancel} className="h-9 rounded-lg border border-border px-3.5 text-[13px]">
          {t("common.cancel")}
        </button>
      </div>
    </section>
  );
}
