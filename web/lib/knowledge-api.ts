import { API_BASE } from "./api";
import type {
  KnowledgeBase,
  KnowledgeFile,
  KnowledgeProgress,
  LinkedFolder,
} from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return (await response.json()) as T;
}

const body = (value: unknown) => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(value ?? {}),
});

export const knowledgeApi = {
  list: () => fetch(`${API_BASE}/knowledge-bases`).then(json<KnowledgeBase[]>),
  get: (id: string) => fetch(`${API_BASE}/knowledge-bases/${id}`).then(json<KnowledgeBase>),
  create: (payload: {
    name: string;
    mode?: "import" | "link";
    embedding_model_id?: string;
    description?: string;
    chunk_size?: number;
    chunk_overlap?: number;
  }) => fetch(`${API_BASE}/knowledge-bases`, body(payload)).then(json<KnowledgeBase>),
  update: (id: string, payload: { name?: string; description?: string; chunk_size?: number; chunk_overlap?: number }) =>
    fetch(`${API_BASE}/knowledge-bases/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }).then(json<KnowledgeBase>),
  remove: (id: string) =>
    fetch(`${API_BASE}/knowledge-bases/${id}`, { method: "DELETE" }),
  files: (id: string) =>
    fetch(`${API_BASE}/knowledge-bases/${id}/files`).then(json<KnowledgeFile[]>),
  removeFile: (id: string, path: string) =>
    fetch(`${API_BASE}/knowledge-bases/${id}/files/${path}`, { method: "DELETE" }),
  addFolder: (id: string, folder: string, mode: "import" | "link" = "import") =>
    fetch(`${API_BASE}/knowledge-bases/${id}/folders`, body({ folder, mode })).then(
      json<KnowledgeBase>,
    ),
  removeFolder: (id: string, folderId: string) =>
    fetch(`${API_BASE}/knowledge-bases/${id}/linked-folders/${folderId}`, {
      method: "DELETE",
    }).then(json<KnowledgeBase>),
  reindex: (id: string) =>
    fetch(`${API_BASE}/knowledge-bases/${id}/reindex`, body({})).then(
      json<{ status: string; total_files?: number; run_id?: string }>,
    ),
  progress: (id: string) =>
    fetch(`${API_BASE}/knowledge-bases/${id}/progress`).then(json<KnowledgeProgress>),
  upload: (id: string, files: File[], paths: string[], conflict = "overwrite") => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file, file.name));
    form.append("paths", JSON.stringify(paths));
    form.append("conflict", conflict);
    return fetch(`${API_BASE}/knowledge-bases/${id}/upload`, {
      method: "POST",
      body: form,
    }).then(json<{ uploaded: number; status: string; total_files?: number; run_id?: string }>);
  },
};

export type { KnowledgeBase, KnowledgeFile, KnowledgeProgress, LinkedFolder };
