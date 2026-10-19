import type { CatalogProvider } from "@/lib/types";

export type { CatalogProvider };

/**
 * A small, common vendor catalog used before the backend catalog arrives (and
 * if it cannot be reached). The backend serves the authoritative list at
 * `GET /settings/providers/catalog`; this fallback mirrors it.
 */
export const PROVIDER_CATALOG: CatalogProvider[] = [
  { id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com", protocol: "openai", services: ["llm", "task"], requires_key: true, monogram: "DS" },
  { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1", protocol: "openai", services: ["llm", "task", "embedding"], requires_key: true, monogram: "OA" },
  { id: "anthropic", name: "Anthropic", base_url: "https://api.anthropic.com", protocol: "anthropic", services: ["llm", "task"], requires_key: true, monogram: "AN" },
  { id: "azure", name: "Azure OpenAI", base_url: "", protocol: "openai", services: ["llm", "task", "embedding"], requires_key: true, monogram: "AZ" },
  { id: "ollama", name: "Ollama", base_url: "http://127.0.0.1:11434/v1", protocol: "ollama", services: ["llm", "task", "embedding"], requires_key: false, monogram: "OL" },
  { id: "custom", name: "Custom", base_url: "", protocol: "custom", services: ["llm", "task", "embedding"], requires_key: true, monogram: "CU" },
];

export function catalogProvider(id: string): CatalogProvider | undefined {
  return PROVIDER_CATALOG.find((provider) => provider.id === id);
}
