import type {
  ChatResponse, DocumentInfo, QuizHealth, QuizResponse, ReadyInfo, SearchResponse, Stats, Suggestion, TopicsResponse, UploadResponse,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public code: string, public status: number, public requestId?: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(`Cannot reach the backend at ${BASE}. Is it running? (See the README, "Start the backend".)`, "network", 0);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    const detail = err?.details?.[0] ? ` (${err.details[0].field}: ${err.details[0].problem})` : "";
    throw new ApiError((err?.message ?? `Request failed (HTTP ${res.status}).`) + detail, err?.code ?? "http_error", res.status, err?.request_id);
  }
  return body as T;
}

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  ready: () => request<ReadyInfo>("/api/v1/ready"),
  stats: () => request<Stats>("/api/v1/stats"),
  documents: () => request<DocumentInfo[]>("/api/v1/documents"),
  deleteDocument: (id: string) => request<void>(`/api/v1/documents/${id}`, { method: "DELETE" }),
  search: (query: string, documentIds: string[], topK: number) =>
    request<SearchResponse>("/api/v1/search", json({ query, top_k: topK, document_ids: documentIds.length ? documentIds : null })),
  chat: (question: string, documentIds: string[]) =>
    request<ChatResponse>("/api/v1/chat", json({ question, document_ids: documentIds.length ? documentIds : null })),
  topics: () => request<TopicsResponse>("/api/v1/topics"),
  suggestions: (documentIds: string[]) => {
    const params = new URLSearchParams({ limit: "6" });
    documentIds.forEach((id) => params.append("document_ids", id));
    return request<Suggestion[]>(`/api/v1/suggestions?${params.toString()}`);
  },
  quizHealth: () => request<QuizHealth>("/api/v1/quiz/health"),
  generateQuiz: (documentIds: string[], topic: string, numQuestions: number, kind: "mcq" | "short_answer") =>
    request<QuizResponse>("/api/v1/quiz/generate", json({ document_ids: documentIds.length ? documentIds : null, topic: topic.trim() || null, num_questions: numQuestions, kind })),

  /** Uses XMLHttpRequest because fetch cannot report upload progress. */
  uploadDocuments(files: File[], onProgress: (fraction: number) => void): Promise<UploadResponse> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      xhr.open("POST", `${BASE}/api/v1/documents`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onerror = () => reject(new ApiError(`Cannot reach the backend at ${BASE}. Is it running?`, "network", 0));
      xhr.onload = () => {
        let body: any = null;
        try { body = JSON.parse(xhr.responseText); } catch { /* fall through */ }
        if (body?.results) return resolve(body as UploadResponse); // 200/201/400 all carry per-file results
        const err = body?.error;
        reject(new ApiError(err?.message ?? `Upload failed (HTTP ${xhr.status}).`, err?.code ?? "http_error", xhr.status, err?.request_id));
      };
      xhr.send(form);
    });
  },
};
