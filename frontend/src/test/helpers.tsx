import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import type { DocumentInfo } from "../types";

export const renderAt = (ui: ReactElement, path = "/") => render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);

export const makeDoc = (over: Partial<DocumentInfo> = {}): DocumentInfo => ({
  id: "doc-1", filename: "syllabus.pdf", file_hash: "abc123", size_bytes: 180452, uploaded_at: "2026-10-20T10:00:00Z",
  page_count: 8, char_count: 8521, chunk_count: 8, status: "Ready", error_message: null, embedding_model: "all-MiniLM-L6-v2", ...over,
});
