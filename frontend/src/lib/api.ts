import type {
  AppConfig,
  AskResponse,
  DocType,
  DocumentContent,
  Project,
  ProjectDocument,
  RetrievalMode,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError("Could not reach the ProjectPulse server. Check that it is running.", 0);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? "Some fields are invalid. Please check your input."
          : res.status >= 500
            ? "The server hit an error. Please try again."
            : `Request failed (${res.status}).`;
    throw new ApiError(message, res.status);
  }
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: JSON.stringify(data),
});

export const api = {
  config: () => request<AppConfig>("/config"),
  projects: () => request<Project[]>("/projects"),
  createProject: (name: string, description = "") => request<Project>("/projects", json("POST", { name, description })),
  sampleProject: (reset = false) =>
    request<Project>(`/projects/sample${reset ? "?reset=true" : ""}`, { method: "POST" }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  suggested: (id: string) =>
    request<{ questions: string[]; precomputed: boolean }>(`/projects/${id}/suggested-questions`),
  documents: (projectId: string) => request<ProjectDocument[]>(`/projects/${projectId}/documents`),
  upload: (projectId: string, file: File, docType: DocType, reportingDate: string | null) => {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    if (reportingDate) form.append("reporting_date", reportingDate);
    return request<ProjectDocument>(`/projects/${projectId}/documents`, { method: "POST", body: form });
  },
  updateDocument: (id: string, data: { doc_type?: DocType; reporting_date?: string }) =>
    request<ProjectDocument>(`/documents/${id}`, json("PATCH", data)),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  documentContent: (id: string) => request<DocumentContent>(`/documents/${id}/content`),
  ask: (projectId: string, question: string, mode: RetrievalMode) =>
    request<AskResponse>(`/projects/${projectId}/ask`, json("POST", { question, mode })),
};
