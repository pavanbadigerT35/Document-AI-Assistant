import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    ready: vi.fn(), stats: vi.fn(), documents: vi.fn(), deleteDocument: vi.fn(), search: vi.fn(), chat: vi.fn(),
    topics: vi.fn(), suggestions: vi.fn(), quizHealth: vi.fn(), generateQuiz: vi.fn(), uploadDocuments: vi.fn(),
  },
}));
vi.mock("../api/client", () => ({ api, ApiError: class extends Error {} }));

import App from "../App";
import Chat from "../pages/Chat";
import Library from "../pages/Library";
import Quiz from "../pages/Quiz";
import SearchPage from "../pages/SearchPage";
import Topics from "../pages/Topics";
import { newId } from "../lib";
import { SourceCard } from "../components/SourceCard";
import type { UploadResult } from "../types";
import { makeDoc, renderAt } from "./helpers";

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  localStorage.clear();
  api.documents.mockResolvedValue([makeDoc()]);
  api.suggestions.mockResolvedValue([]);
  api.ready.mockResolvedValue({ status: "ok", checks: { llm: { configured: true, model: "m", message: null }, embeddings: { model: "x/MiniLM", loaded: true } } });
});

const meta = { top_k: 5, min_score: 0.25, candidates: 5, above_threshold: 1, top_score: 0.61, latency_ms: 12 };

describe("Document library", () => {
  it("lists documents with status badges and shows failure reasons", async () => {
    api.documents.mockResolvedValue([makeDoc(), makeDoc({ id: "d2", filename: "scan.pdf", status: "Failed", error_message: "looks like a scanned PDF", page_count: 3, chunk_count: 0 })]);
    renderAt(<Library />);
    expect(await screen.findByText("syllabus.pdf")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "scan.pdf" }));
    expect(screen.getByRole("alert")).toHaveTextContent("scanned PDF");
  });

  it("shows an empty state when there are no documents", async () => {
    api.documents.mockResolvedValue([]);
    renderAt(<Library />);
    expect(await screen.findByText("Your library is empty")).toBeInTheDocument();
  });

  it("shows a loading state, then an error state with retry", async () => {
    api.documents.mockRejectedValue(new Error("Cannot reach the backend"));
    renderAt(<Library />);
    expect(screen.getByText("Loading documents…")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the backend");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("reports a duplicate upload clearly", async () => {
    api.uploadDocuments.mockResolvedValue({ results: [{ filename: "again.pdf", outcome: "duplicate", message: "Already indexed as 'syllabus.pdf'. Nothing was added.", document: makeDoc() }] });
    renderAt(<Library />);
    await screen.findByText("syllabus.pdf");
    const file = new File(["%PDF-1.4"], "again.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("PDF files to upload"), file);
    expect(await screen.findByText(/Already indexed as 'syllabus.pdf'/)).toBeInTheDocument();
    expect(api.uploadDocuments).toHaveBeenCalledTimes(1);
  });

  it("automatically dismisses upload results after 25 seconds", async () => {
    api.uploadDocuments.mockResolvedValue({ results: [{ filename: "again.pdf", outcome: "duplicate", message: "Already indexed as 'syllabus.pdf'. Nothing was added.", document: makeDoc() }] });
    renderAt(<Library />);
    await screen.findByText("syllabus.pdf");
    const timeoutSpy = vi.spyOn(window, "setTimeout");
    try {
      const file = new File(["%PDF-1.4"], "again.pdf", { type: "application/pdf" });
      await userEvent.upload(screen.getByLabelText("PDF files to upload"), file);
      await screen.findByText(/Already indexed/);
      expect(screen.getByRole("list", { name: "Upload results" })).toHaveTextContent("Already indexed");
      const dismissTimer = timeoutSpy.mock.calls.find(([, delay]) => delay === 25_000)?.[0];
      expect(typeof dismissTimer).toBe("function");
      act(() => { if (typeof dismissTimer === "function") dismissTimer(); });
      expect(screen.queryByRole("list", { name: "Upload results" })).not.toBeInTheDocument();
    } finally {
      timeoutSpy.mockRestore();
    }
  });

  it("shows animated estimated progress while indexing", async () => {
    let finishUpload: ((response: { results: UploadResult[] }) => void) | undefined;
    api.uploadDocuments.mockImplementation((_files, onProgress) => {
      onProgress(1);
      return new Promise((resolve) => { finishUpload = resolve; });
    });
    renderAt(<Library />);
    await screen.findByText("syllabus.pdf");
    const file = new File(["%PDF-1.4"], "new.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("PDF files to upload"), file);

    expect(await screen.findByText("Indexing… 10%")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "12"), { timeout: 1500 });

    finishUpload?.({ results: [] });
    await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
  });

  it("deletes only after confirmation", async () => {
    api.deleteDocument.mockResolvedValue(undefined);
    renderAt(<Library />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete syllabus.pdf" }));
    expect(api.deleteDocument).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith("doc-1"));
  });
});

describe("Source citations", () => {
  it("renders filename, page number and highlights query words", () => {
    renderAt(<SourceCard documentId="d" filename="syllabus.pdf" page={6} text="Self-healing automation handles locator changes." query="locator changes" />);
    expect(screen.getByLabelText("Source: syllabus.pdf, page 6")).toBeInTheDocument();
    expect(screen.getByText("page 6")).toBeInTheDocument();
    expect(screen.getByText("locator").tagName).toBe("MARK");
  });
});

describe("Knowledge search", () => {
  it("sends the selected scope and shows ranked passages", async () => {
    api.search.mockResolvedValue({ results: [{ chunk_id: "c1", document_id: "doc-1", filename: "syllabus.pdf", page: 7, text: "API test generation from Swagger", score: 0.52 }], retrieval: meta });
    renderAt(<SearchPage />);
    await userEvent.type(screen.getByLabelText("Search query"), "swagger");
    await userEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    expect(await screen.findByText("page 7")).toBeInTheDocument();
    expect(api.search).toHaveBeenCalledWith("swagger", [], 5);
  });

  it("filters to a single document when one is selected", async () => {
    api.search.mockResolvedValue({ results: [], retrieval: meta });
    renderAt(<SearchPage />);
    await userEvent.click(await screen.findByLabelText(/Search scope/));
    await userEvent.click(await screen.findByRole("checkbox", { name: /syllabus\.pdf/ }));
    await userEvent.type(screen.getByLabelText("Search query"), "anything");
    await userEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => expect(api.search).toHaveBeenCalledWith("anything", ["doc-1"], 5));
  });

  it("closes the scope menu on outside click and remembers the selected documents", async () => {
    const user = userEvent.setup();
    const { unmount } = renderAt(<SearchPage />);
    const scope = await screen.findByLabelText(/Search scope/);
    await user.click(scope);
    await user.click(screen.getByRole("checkbox", { name: /syllabus\.pdf/ }));
    await user.click(screen.getByLabelText("Search query"));
    expect(scope.closest("details")).not.toHaveAttribute("open");
    expect(scope).toHaveTextContent("syllabus.pdf");

    unmount();
    renderAt(<SearchPage />);
    expect(await screen.findByLabelText(/Search scope: syllabus\.pdf/)).toBeInTheDocument();
  });

  it("shows a no-results state that explains the threshold", async () => {
    api.search.mockResolvedValue({ results: [], retrieval: { ...meta, top_score: 0.11, above_threshold: 0 } });
    renderAt(<SearchPage />);
    await userEvent.type(screen.getByLabelText("Search query"), "refund policy");
    await userEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    expect(await screen.findByText("No matching passages")).toBeInTheDocument();
    expect(screen.getByText(/closest passage scored 0.11/)).toBeInTheDocument();
  });
});

describe("AI chat", () => {
  async function ask(q: string) {
    renderAt(<Chat />);
    const box = screen.getByLabelText("Your question");
    await waitFor(() => expect(box).toBeEnabled());
    await userEvent.type(box, q);
    await userEvent.click(screen.getByRole("button", { name: /Ask/ }));
  }

  it("shows the answer with a citation chip and a source card", async () => {
    api.chat.mockResolvedValue({
      answer: "Self-healing handles locator changes [S1].", insufficient_evidence: false, warning: null, retrieval: meta, llm: { provider: "groq", model: "m" },
      sources: [{ source_id: "S1", chunk_id: "c", document_id: "doc-1", filename: "syllabus.pdf", page: 6, excerpt: "Handling locator changes", score: 0.6 }],
    });
    await ask("What is self-healing?");
    const sources = await screen.findByRole("button", { name: "Sources (1)" });
    expect(sources).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByLabelText("Source: syllabus.pdf, page 6")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "S1" }));
    expect(sources).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Source: syllabus.pdf, page 6")).toBeInTheDocument();
    expect(screen.getAllByText("S1").length).toBeGreaterThanOrEqual(2); // chip + card label
    await userEvent.click(sources);
    expect(sources).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByLabelText("Source: syllabus.pdf, page 6")).not.toBeInTheDocument();
    expect(api.chat).toHaveBeenCalledWith("What is self-healing?", []);
  });

  it("lets users edit a previous question and copy it", async () => {
    api.chat.mockResolvedValue({
      answer: "A helpful answer.", insufficient_evidence: false, warning: null, retrieval: meta, llm: null, sources: [],
    });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    await ask("What is self-healing?");
    const editButton = await screen.findByRole("button", { name: "Edit question: What is self-healing?" });
    await userEvent.click(editButton);
    const composer = screen.getByRole("textbox", { name: "Your question" });
    expect(composer).toHaveValue("What is self-healing?");
    expect(composer).toHaveFocus();

    await userEvent.clear(composer);
    await userEvent.type(composer, "How does self-healing work?");
    await userEvent.click(screen.getByRole("button", { name: /^Ask/ }));
    await waitFor(() => expect(api.chat).toHaveBeenLastCalledWith("How does self-healing work?", []));

    await userEvent.click(screen.getByRole("button", { name: "Copy question: What is self-healing?" }));
    expect(writeText).toHaveBeenCalledWith("What is self-healing?");
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("states clearly when evidence is insufficient", async () => {
    api.chat.mockResolvedValue({ answer: "I couldn't find enough information in the selected documents to answer that.", insufficient_evidence: true, warning: null, sources: [], retrieval: meta, llm: null });
    await ask("What is the refund policy?");
    expect(await screen.findByText(/Not enough evidence/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sources" })).not.toBeInTheDocument();
  });

  it("shows request failures as an error", async () => {
    api.chat.mockRejectedValue(new Error("GROQ_API_KEY is not set."));
    await ask("hello there");
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/GROQ_API_KEY is not set/)).toBeInTheDocument();
  });

  it("offers suggestions built from the documents", async () => {
    api.suggestions.mockResolvedValue([{ question: "How does Prompt Engineering for QA work?", document_id: "doc-1", filename: "syllabus.pdf", page: 2 }]);
    api.chat.mockResolvedValue({ answer: "The section explains the process.", insufficient_evidence: false, warning: null, sources: [], retrieval: meta, llm: null });
    renderAt(<Chat />);
    const suggestion = await screen.findByRole("button", { name: "How does Prompt Engineering for QA work?" });
    await userEvent.click(suggestion);
    await waitFor(() => expect(api.chat).toHaveBeenCalledWith("How does Prompt Engineering for QA work?", []));
  });
});

describe("Quiz", () => {
  it("disables generation and explains why when the LLM is not configured", async () => {
    api.quizHealth.mockResolvedValue({ available: false, reason: "Quiz generation needs an LLM. Set GROQ_API_KEY." });
    renderAt(<Quiz />);
    expect(await screen.findByText(/Set GROQ_API_KEY/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate questions" })).toBeDisabled();
  });

  it("generates questions, labels them as AI-created and reveals answers with sources", async () => {
    api.quizHealth.mockResolvedValue({ available: true, reason: null });
    api.generateQuiz.mockResolvedValue({
      label: "AI-generated learning content. Not official exam questions.",
      questions: [{ question: "Which module covers RTM?", options: ["Module 3", "Module 5", "Module 7", "Module 9"], correct_index: 1, answer: null, explanation: "RTM is in 5.3.", source: { chunk_id: "c", document_id: "doc-1", filename: "syllabus.pdf", page: 5, excerpt: "RTM" } }],
    });
    renderAt(<Quiz />);
    const button = screen.getByRole("button", { name: "Generate questions" });
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.click(button);
    expect(await screen.findByText(/Not official exam questions/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reveal answer" }));
    expect(screen.getByText(/RTM is in 5.3/)).toBeInTheDocument();
    expect(screen.getByText(/syllabus.pdf, page 5/)).toBeInTheDocument();
  });
});

describe("Topic explorer", () => {
  const topics = {
    grouping: "heuristic", note: "Topics are detected heuristically from headings and may be incomplete.",
    documents: [{ document_id: "doc-1", filename: "syllabus.pdf", topics: [{ title: "Module 6: Responsible AI", page: 6, level: 1 }, { title: "6.1 AI Output Validation", page: 6, level: 2 }] }],
  };

  it("labels the grouping as heuristic and links each topic to search and to a quiz", async () => {
    api.topics.mockResolvedValue(topics);
    renderAt(<Topics />);
    expect(await screen.findByText(/detected heuristically/)).toBeInTheDocument();
    expect(screen.getByText("6.1 AI Output Validation")).toBeInTheDocument();
    const searchLink = screen.getAllByRole("link").find((l) => l.getAttribute("href")?.startsWith("/search?q=Module%206"));
    expect(searchLink).toHaveAttribute("href", "/search?q=Module%206%3A%20Responsible%20AI&doc=doc-1");
    expect(screen.getByRole("link", { name: "Quiz me on Module 6: Responsible AI" })).toHaveAttribute("href", "/quiz?topic=Module%206%3A%20Responsible%20AI&doc=doc-1");
  });

  it("shows an empty state when nothing is indexed", async () => {
    api.topics.mockResolvedValue({ ...topics, documents: [] });
    renderAt(<Topics />);
    expect(await screen.findByText("No topics yet")).toBeInTheDocument();
  });
});

describe("Quiz from a topic link", () => {
  it("pre-fills the topic and document from the URL and sends them", async () => {
    api.quizHealth.mockResolvedValue({ available: true, reason: null });
    api.generateQuiz.mockResolvedValue({ label: "AI-generated learning content.", questions: [] });
    renderAt(<Quiz />, "/quiz?topic=Module%206&doc=doc-1");
    expect(screen.getByLabelText(/Topic \(optional\)/)).toHaveValue("Module 6");
    const button = screen.getByRole("button", { name: "Generate questions" });
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.click(button);
    await waitFor(() => expect(api.generateQuiz).toHaveBeenCalledWith(["doc-1"], "Module 6", 5, "mcq"));
    await userEvent.selectOptions(screen.getByLabelText("Question type"), "short_answer");
    await userEvent.click(button);
    await waitFor(() => expect(api.generateQuiz).toHaveBeenLastCalledWith(["doc-1"], "Module 6", 5, "short_answer"));
  });
});

describe("newId", () => {
  it("falls back to a random id when crypto.randomUUID is unavailable", () => {
    const a = newId({}), b = newId({});
    expect(a).toMatch(/^[a-z0-9]+-[a-z0-9]+$/);
    expect(a).not.toEqual(b);
  });
  it("uses crypto.randomUUID when it exists", () => {
    expect(newId({ randomUUID: () => "fixed-id" })).toBe("fixed-id");
  });
});

describe("App shell", () => {
  it("renders navigation and the dashboard with real statistics", async () => {
    api.stats.mockResolvedValue({ total_documents: 2, ready_documents: 1, failed_documents: 1, total_pages: 8, total_chunks: 8, recent_documents: [makeDoc()], recent_activity: [{ timestamp: "2026-10-20T10:00:00Z", kind: "upload", message: "Indexed syllabus.pdf (8 pages, 8 chunks)" }], llm_configured: false });
    renderAt(<App />);
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    for (const name of ["Document library", "Knowledge search", "AI chat", "Topic explorer", "Quiz and revision"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(await screen.findByText("Indexed and searchable")).toBeInTheDocument();
    expect(screen.getByText(/no Groq API key is set/)).toBeInTheDocument();
  });
});
