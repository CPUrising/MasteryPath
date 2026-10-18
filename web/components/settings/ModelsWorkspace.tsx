"use client";

import { useEffect, useState } from "react";
import { Check, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { AddModelPanel, type NewModelInput } from "./AddModelPanel";
import { Field, SettingsPageHeader, TextInput } from "./shared";
import { WorkspaceDetailEmpty, WorkspaceRail, WorkspaceSplit, workspaceCardClass } from "./WorkspaceShell";
import { api } from "@/lib/api";
import type { ModelEntry, ModelSection, Provider } from "@/lib/types";

export type ModelPage = "llm" | "task-models" | "embedding";

const TITLES: Record<ModelPage, { title: string; desc: string }> = {
  llm: { title: "settings.llm.title", desc: "settings.llm.desc" },
  "task-models": { title: "settings.task.title", desc: "settings.task.desc" },
  embedding: { title: "settings.embedding.title", desc: "settings.embedding.desc" },
};

export function ModelsWorkspace({ page }: { page: ModelPage }) {
  const { t } = useTranslation();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [section, setSection] = useState<ModelSection>({ models: [], active_id: "" });
  const [selected, setSelected] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getProviders().then(setProviders).catch(() => setProviders([]));
    api.getSettings(page).then((value) => setSection(value as ModelSection)).catch(() => undefined);
  }, [page]);

  const providerName = (id: string) =>
    providers.find((provider) => provider.id === id)?.name || id || "—";

  const persist = async (next: ModelSection) => {
    setSection(next);
    try {
      await api.putSettings(page, next);
      setSaved(true);
      setError("");
      window.setTimeout(() => setSaved(false), 1500);
    } catch (reason) {
      setError(String(reason));
    }
  };

  const selectedModel = section.models.find((entry) => entry.id === selected);
  const filtered = section.models.filter((entry) =>
    `${entry.name} ${entry.model} ${providerName(entry.provider_id)}`.toLowerCase().includes(query.toLowerCase()),
  );
  const withDimension = page === "embedding";

  const create = (input: NewModelInput) => {
    const entry: ModelEntry = { id: `m-${Date.now().toString(36)}`, ...input };
    void persist({ models: [...section.models, entry], active_id: section.active_id || entry.id });
    setSelected(entry.id);
    setAdding(false);
  };

  if (adding) {
    return (
      <div>
        <SettingsPageHeader title={t(TITLES[page].title)} description={t(TITLES[page].desc)} />
        <AddModelPanel providers={providers} withDimension={withDimension} onCancel={() => setAdding(false)} onCreate={create} />
      </div>
    );
  }

  return (
    <div>
      <SettingsPageHeader title={t(TITLES[page].title)} description={t(TITLES[page].desc)} />
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
                {t("settings.addModel")}
              </button>
            }
            search={{ label: t("settings.findModel"), value: query, onChange: setQuery, placeholder: t("settings.findModel") }}
            empty={
              filtered.length ? undefined : section.models.length ? t("settings.noModelMatch") : t("settings.noModels")
            }
          >
            {filtered.map((entry) => (
              <button
                key={entry.id}
                type="button"
                aria-pressed={entry.id === selected}
                onClick={() => setSelected(entry.id)}
                className={workspaceCardClass(entry.id === selected)}
              >
                <span className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{entry.name}</span>
                  {entry.id === section.active_id && (
                    <span className="inline-flex shrink-0 items-center gap-0.5 text-[11px] text-primary">
                      <Check size={13} />
                      {t("settings.default")}
                    </span>
                  )}
                </span>
                <span className="mt-1 block truncate text-[12px] text-muted-foreground">
                  {providerName(entry.provider_id)} · {entry.model}
                </span>
              </button>
            ))}
          </WorkspaceRail>
        }
        detail={
          selectedModel ? (
            <section className="min-w-0 rounded-2xl border border-primary/30 bg-card p-5">
              <header className="mb-5">
                <p className="text-[12px] font-medium text-primary">{t("settings.configuringModel")}</p>
                <h3 className="mt-0.5 text-base font-semibold">{selectedModel.name}</h3>
                <p className="mt-0.5 text-[13px] text-muted-foreground">{providerName(selectedModel.provider_id)}</p>
              </header>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("settings.provider")}>
                  <select
                    value={selectedModel.provider_id}
                    onChange={(event) =>
                      void persist({
                        ...section,
                        models: section.models.map((entry) =>
                          entry.id === selectedModel.id ? { ...entry, provider_id: event.target.value } : entry,
                        ),
                      })
                    }
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
                  <TextInput
                    value={selectedModel.model}
                    onChange={(value) =>
                      setSection({
                        ...section,
                        models: section.models.map((entry) =>
                          entry.id === selectedModel.id ? { ...entry, model: value } : entry,
                        ),
                      })
                    }
                  />
                </Field>
                {withDimension && (
                  <Field label="dimension">
                    <TextInput
                      value={String(selectedModel.dimension ?? 0)}
                      onChange={(value) =>
                        setSection({
                          ...section,
                          models: section.models.map((entry) =>
                            entry.id === selectedModel.id ? { ...entry, dimension: Number(value) || 0 } : entry,
                          ),
                        })
                      }
                    />
                  </Field>
                )}
              </div>
              <div className="mt-5 flex items-center gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  onClick={() => persist(section)}
                  className="h-9 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-primary-foreground"
                >
                  {saved ? t("settings.saved") : t("settings.save")}
                </button>
                {error && <span className="text-[12px] text-destructive">{t("settings.saveFailed")}</span>}
                <button
                  type="button"
                  disabled={section.active_id === selectedModel.id}
                  onClick={() => persist({ ...section, active_id: selectedModel.id })}
                  className="h-9 rounded-lg border border-border px-3.5 text-[13px] disabled:opacity-50"
                >
                  {t("settings.setDefault")}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void persist({
                      models: section.models.filter((entry) => entry.id !== selectedModel.id),
                      active_id: section.active_id === selectedModel.id ? "" : section.active_id,
                    });
                    setSelected(null);
                  }}
                  className="ml-auto inline-flex items-center gap-1.5 text-[13px] text-destructive hover:underline"
                >
                  <Trash2 size={13} />
                  {t("settings.removeModel")}
                </button>
              </div>
            </section>
          ) : (
            <WorkspaceDetailEmpty
              icon={<SlidersHorizontal size={17} />}
              title={t("settings.nothingSelected")}
              hint={t("settings.selectModelHint")}
            />
          )
        }
      />
    </div>
  );
}
