export interface CatalogProvider {
  id: string;
  name: string;
  base_url: string;
  requires_key: boolean;
  /** Two-letter monogram shown when there is no brand icon. */
  monogram: string;
}

/** A small, common vendor catalog (DeepTutor ships a much larger registry). */
export const PROVIDER_CATALOG: CatalogProvider[] = [
  { id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com", requires_key: true, monogram: "DS" },
  { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1", requires_key: true, monogram: "OA" },
  { id: "anthropic", name: "Anthropic", base_url: "https://api.anthropic.com", requires_key: true, monogram: "AN" },
  { id: "azure", name: "Azure OpenAI", base_url: "", requires_key: true, monogram: "AZ" },
  { id: "ollama", name: "Ollama", base_url: "http://127.0.0.1:11434/v1", requires_key: false, monogram: "OL" },
  { id: "custom", name: "自定义", base_url: "", requires_key: true, monogram: "··" },
];

export function catalogProvider(id: string): CatalogProvider | undefined {
  return PROVIDER_CATALOG.find((provider) => provider.id === id);
}
