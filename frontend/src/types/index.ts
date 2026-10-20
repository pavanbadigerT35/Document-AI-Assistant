export type DocStatus = "Pending" | "Processing" | "Ready" | "Failed";

export interface DocumentInfo {
  id: string; filename: string; file_hash: string; size_bytes: number; uploaded_at: string;
  page_count: number; char_count: number; chunk_count: number; status: DocStatus;
  error_message: string | null; embedding_model: string | null;
}
export interface UploadResult { filename: string; outcome: "created" | "duplicate" | "failed" | "rejected"; message: string; document: DocumentInfo | null }
export interface UploadResponse { results: UploadResult[]; request_id?: string }
export interface Activity { timestamp: string; kind: string; message: string }
export interface Stats {
  total_documents: number; ready_documents: number; failed_documents: number; total_pages: number; total_chunks: number;
  recent_documents: DocumentInfo[]; recent_activity: Activity[]; llm_configured: boolean;
}
export interface Passage { chunk_id: string; document_id: string; filename: string; page: number; text: string; score: number }
export interface RetrievalMeta { top_k: number; min_score: number; candidates: number; above_threshold: number; top_score: number | null; latency_ms: number }
export interface SearchResponse { results: Passage[]; retrieval: RetrievalMeta; request_id?: string }
export interface Source { source_id: string; chunk_id: string; document_id: string; filename: string; page: number; excerpt: string; score: number }
export interface ChatResponse {
  answer: string; sources: Source[]; insufficient_evidence: boolean; warning: string | null;
  retrieval: RetrievalMeta; llm: { provider: string; model: string } | null; request_id?: string;
}
export interface TopicItem { title: string; page: number; level: number }
export interface DocumentTopics { document_id: string; filename: string; topics: TopicItem[] }
export interface TopicsResponse { grouping: string; note: string; documents: DocumentTopics[] }
export interface Suggestion { question: string; document_id: string; filename: string; page: number }
export interface QuizQuestion {
  question: string; options: string[]; correct_index: number | null; answer: string | null; explanation: string;
  source: { chunk_id: string; document_id: string; filename: string; page: number; excerpt: string };
}
export interface QuizResponse { label: string; questions: QuizQuestion[] }
export interface QuizHealth { available: boolean; reason: string | null }
export interface ReadyInfo { status: string; checks: { llm: { configured: boolean; model: string; message: string | null }; embeddings: { model: string; loaded: boolean } } }
