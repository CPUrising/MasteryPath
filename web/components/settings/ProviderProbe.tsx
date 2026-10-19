"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, PlugZap } from "lucide-react";
import { useTranslation } from "react-i18next";

import { api, type ProbeInput } from "@/lib/api";
import type { DetectedModel, ProviderDetection } from "@/lib/types";

const STATUS_KEYS: Record<string, string> = {
  connected: "settings.probe.connected",
  auth_error: "settings.probe.authError",
  unavailable: "settings.probe.unavailable",
  rate_limited: "settings.probe.rateLimited",
  timeout: "settings.probe.timeout",
  unreachable: "settings.probe.unreachable",
  invalid_url: "settings.probe.invalidUrl",
  http_error: "settings.probe.httpError",
};

/**
 * Test a provider connection and list its models, without a billable call.
 *
 * Calls the backend probe, which resolves any omitted credential from the saved
 * provider named by `provider_id`. Give this component a `key` derived from the
 * fields so a changed credential remounts and cancels stale results.
 */
export function ProviderProbe({
  fields,
  onResult,
  onAdd,
  addedIds = [],
  defaultOpen = false,
}: {
  fields: ProbeInput;
  onResult?: (result: ProviderDetection) => void;
  onAdd?: (models: DetectedModel[]) => void;
  addedIds?: string[];
  defaultOpen?: boolean;
}) {
  const { t } = useTranslation();
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ProviderDetection | null>(null);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<string[]>([]);

  const run = async () => {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      const data = await api.probeProvider(fields);
      setResult(data);
      onResult?.(data);
    } catch (reason) {
      setResult(null);
      setError(String(reason));
    } finally {
      setPending(false);
    }
  };

  const status = result?.status ?? "";
  const connected = status === "connected";
  const addable = (result?.models ?? []).filter((model) => !addedIds.includes(model.id));

  return (
    <div className="space-y-3 border-t border-border pt-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={() => void run()}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-[13px] hover:bg-accent/60 disabled:opacity-50"
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <PlugZap size={14} />}
          {pending ? t("settings.probe.testing") : t("settings.probe.test")}
        </button>
        <span className="text-[12px] text-muted-foreground">{t("settings.probe.hint")}</span>
      </div>

      <div role="status" aria-live="polite" className="text-[13px]">
        {error && <p className="text-destructive">{error}</p>}
        {result && (
          <p className={connected ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}>
            {connected && <CheckCircle2 size={14} className="mr-1 inline" />}
            {t(STATUS_KEYS[status] ?? STATUS_KEYS.http_error)}
            {connected && ` · ${t("settings.probe.modelCount", { count: result.models.length })}`}
            {result.http_status != null && ` · HTTP ${result.http_status}`}
          </p>
        )}
      </div>

      {connected && !!result?.models.length && (
        <details open={defaultOpen} className="rounded-xl border border-border bg-background p-3">
          <summary className="cursor-pointer text-[12px] text-muted-foreground">
            {t("settings.probe.models")}
          </summary>
          <div className="mt-2 max-h-56 overflow-y-auto">
            {result.models.map((model) => {
              const added = addedIds.includes(model.id);
              return (
                <label
                  key={model.id}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[12px] hover:bg-accent/60"
                >
                  {onAdd && (
                    <input
                      type="checkbox"
                      disabled={added}
                      checked={added || picked.includes(model.id)}
                      onChange={(event) =>
                        setPicked((current) =>
                          event.target.checked
                            ? [...current, model.id]
                            : current.filter((id) => id !== model.id),
                        )
                      }
                    />
                  )}
                  <span className="min-w-0 flex-1 truncate font-mono">{model.id}</span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {model.services.join(", ")}
                  </span>
                </label>
              );
            })}
          </div>
          {onAdd && (
            <button
              type="button"
              disabled={!picked.length}
              onClick={() => {
                onAdd(
                  result.models.filter(
                    (model) => picked.includes(model.id) && !addedIds.includes(model.id),
                  ),
                );
                setPicked([]);
              }}
              className="mt-2 h-8 rounded-lg bg-primary px-3 text-[12px] font-medium text-primary-foreground disabled:opacity-50"
            >
              {t("settings.probe.addSelected")}
            </button>
          )}
        </details>
      )}
      {connected && result && !result.models.length && (
        <p className="text-[12px] text-muted-foreground">{t("settings.probe.noModels")}</p>
      )}
    </div>
  );
}
