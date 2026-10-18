"use client";

import { useEffect, useState } from "react";
import { Cable, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { AddProviderPanel, type NewProviderInput } from "./AddProviderPanel";
import { Field, SettingsPageHeader, TextInput } from "./shared";
import { WorkspaceDetailEmpty, WorkspaceRail, WorkspaceSplit, workspaceCardClass } from "./WorkspaceShell";
import { api } from "@/lib/api";
import type { Provider } from "@/lib/types";

export function ProvidersWorkspace() {
  const { t } = useTranslation();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getProviders().then(setProviders).catch(() => setProviders([]));
  }, []);

  const persist = async () => {
    await api.putSettings("providers", providers);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  };

  const source = providers.find((provider) => provider.id === selected);
  const filtered = providers.filter((provider) =>
    `${provider.name} ${provider.id} ${provider.base_url}`.toLowerCase().includes(query.toLowerCase()),
  );

  const create = async (input: NewProviderInput) => {
    const id = `conn-${Date.now().toString(36)}`;
    const entry: Provider = { id, name: input.name, base_url: input.base_url, api_key: "" };
    setProviders((rows) => [...rows, entry]);
    setSelected(id);
    setAdding(false);
  };

  if (adding) {
    return (
      <div>
        <SettingsPageHeader title={t("settings.conn.title")} description={t("settings.conn.desc")} />
        <AddProviderPanel onCancel={() => setAdding(false)} onCreate={create} />
      </div>
    );
  }

  return (
    <div>
      <SettingsPageHeader title={t("settings.conn.title")} description={t("settings.conn.desc")} />
      <WorkspaceSplit
        rail={
          <WorkspaceRail
            action={
              <button
                type="button"
                onClick={() => setAdding(true)}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border py-2 text-[13px] hover:bg-accent/60"
              >
                <Plus size={14} />
                {t("settings.addProvider")}
              </button>
            }
            search={{ label: t("settings.findProvider"), value: query, onChange: setQuery, placeholder: t("settings.findProvider") }}
            empty={
              filtered.length
                ? undefined
                : providers.length
                  ? t("settings.noProviderMatch")
                  : t("settings.addFirstProvider")
            }
          >
            {filtered.map((provider) => (
              <button
                key={provider.id}
                type="button"
                aria-pressed={provider.id === selected}
                onClick={() => setSelected(provider.id)}
                className={workspaceCardClass(provider.id === selected)}
              >
                <span className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded bg-muted text-[10px] font-semibold text-muted-foreground">
                    {(provider.name || provider.id).slice(0, 2).toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[14px] font-medium">
                    {provider.name || provider.id}
                  </span>
                </span>
                <span className="mt-1 block truncate pl-7 text-[12px] text-muted-foreground">
                  {provider.base_url || "—"}
                </span>
              </button>
            ))}
          </WorkspaceRail>
        }
        detail={
          source ? (
            <section className="min-w-0 rounded-2xl border border-primary/30 bg-card p-5">
              <header className="mb-5">
                <p className="text-[12px] font-medium text-primary">{t("settings.configuringProvider")}</p>
                <h3 className="mt-0.5 text-base font-semibold">{source.name || source.id}</h3>
              </header>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("settings.provider.name")}>
                  <TextInput
                    value={source.name}
                    onChange={(value) =>
                      setProviders((rows) => rows.map((row) => (row.id === source.id ? { ...row, name: value } : row)))
                    }
                  />
                </Field>
                <Field label={t("settings.provider.url")}>
                  <TextInput
                    value={source.base_url}
                    onChange={(value) =>
                      setProviders((rows) => rows.map((row) => (row.id === source.id ? { ...row, base_url: value } : row)))
                    }
                  />
                </Field>
                <Field label={t("settings.provider.key")}>
                  <TextInput
                    type="password"
                    value={source.api_key}
                    onChange={(value) =>
                      setProviders((rows) => rows.map((row) => (row.id === source.id ? { ...row, api_key: value } : row)))
                    }
                  />
                </Field>
              </div>
              <div className="mt-5 flex items-center gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  onClick={persist}
                  className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground"
                >
                  {saved ? t("settings.saved") : t("settings.save")}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setProviders((rows) => rows.filter((row) => row.id !== source.id));
                    setSelected(null);
                  }}
                  className="ml-auto inline-flex items-center gap-1.5 text-[13px] text-destructive hover:underline"
                >
                  <Trash2 size={13} />
                  {t("settings.removeProvider")}
                </button>
              </div>
            </section>
          ) : (
            <WorkspaceDetailEmpty icon={<Cable size={17} />} title={t("settings.nothingSelected")} hint={t("settings.selectProviderHint")} />
          )
        }
      />
    </div>
  );
}
