"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Field, TextInput } from "./shared";
import type { Provider } from "@/lib/types";

export interface NewModelInput {
  provider_id: string;
  model: string;
  name: string;
  dimension?: number;
}

/** Add a model by choosing a configured provider, like DeepTutor's Add model. */
export function AddModelPanel({
  providers,
  withDimension,
  onCancel,
  onCreate,
}: {
  providers: Provider[];
  withDimension?: boolean;
  onCancel: () => void;
  onCreate: (input: NewModelInput) => void;
}) {
  const { t } = useTranslation();
  const [providerId, setProviderId] = useState("");
  const [model, setModel] = useState("");
  const [name, setName] = useState("");
  const [dimension, setDimension] = useState("");

  return (
    <section className="min-w-0 space-y-4 rounded-2xl border border-border bg-card p-5">
      <h3 className="text-base font-semibold">{t("settings.addModel")}</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("settings.provider")}>
          <select
            value={providerId}
            onChange={(event) => setProviderId(event.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">{t("settings.chooseProvider")}</option>
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name || provider.id}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("settings.model")}>
          <TextInput value={model} onChange={setModel} />
        </Field>
        <Field label={t("settings.provider.name")}>
          <TextInput value={name} onChange={setName} />
        </Field>
        {withDimension && (
          <Field label="dimension">
            <TextInput value={dimension} onChange={setDimension} />
          </Field>
        )}
      </div>
      <div className="flex gap-2 border-t border-border pt-4">
        <button
          type="button"
          disabled={!providerId || !model.trim()}
          onClick={() =>
            onCreate({
              provider_id: providerId,
              model: model.trim(),
              name: name.trim() || model.trim(),
              dimension: withDimension ? Number(dimension) || 0 : undefined,
            })
          }
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
