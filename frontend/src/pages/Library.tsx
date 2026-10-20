import { ChevronDown, ChevronRight, Trash2, UploadCloud } from "lucide-react";
import { Fragment, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, Notice, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { useDocuments } from "../hooks/useDocuments";
import { errorMessage, formatBytes, formatDate } from "../lib";
import type { UploadResult } from "../types";

const TONE = { created: "success", duplicate: "info", failed: "warn", rejected: "warn" } as const;

export default function Library() {
  const { documents, loading, error, refresh } = useDocuments();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    setBusy(true); setProgress(0); setResults(null); setUploadError(null);
    try {
      setResults((await api.uploadDocuments(list, setProgress)).results);
    } catch (e) {
      setUploadError(errorMessage(e));
    } finally {
      setBusy(false);
      await refresh();
    }
  }

  async function remove(id: string) {
    setDeleteError(null);
    try { await api.deleteDocument(id); setConfirmId(null); await refresh(); }
    catch (e) { setDeleteError(errorMessage(e)); }
  }

  return (
    <>
      <PageHeader title="Document library">Upload PDFs to index them. Text-based PDFs only; scanned pages need OCR, which is not included.</PageHeader>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void handleFiles(e.dataTransfer.files); }}
        className={`mb-4 flex flex-col items-center gap-3 rounded-md border-2 border-dashed px-6 py-8 text-center ${dragging ? "border-signal bg-signal-tint" : "border-line bg-white"}`}
      >
        <UploadCloud className="h-8 w-8 text-signal" aria-hidden />
        <p className="text-sm text-ink-soft">Drag PDF files here, or</p>
        <button className="btn-primary" onClick={() => input.current?.click()} disabled={busy}>Choose PDF files</button>
        <input ref={input} type="file" accept=".pdf,application/pdf" multiple hidden aria-label="PDF files to upload" onChange={(e) => { void handleFiles(e.target.files ?? []); e.target.value = ""; }} />
      </div>

      {busy && (
        <div className="mb-4" role="status">
          <p className="mb-1 text-sm">{progress < 1 ? `Uploading… ${Math.round(progress * 100)}%` : "Indexing: extracting text and building embeddings. The first run downloads the embedding model, which can take a minute."}</p>
          <progress className="h-2 w-full" value={progress < 1 ? progress : undefined} max={1} aria-label="Upload progress" />
        </div>
      )}
      {uploadError && <div className="mb-4"><ErrorNotice>{uploadError}</ErrorNotice></div>}
      {results && (
        <ul className="mb-6 space-y-2" aria-label="Upload results">
          {results.map((r, i) => (
            <li key={i}><Notice tone={TONE[r.outcome]}><strong>{r.filename}</strong>: {r.message}</Notice></li>
          ))}
        </ul>
      )}

      {loading ? <Spinner label="Loading documents…" /> : error ? <ErrorNotice onRetry={refresh}>{error}</ErrorNotice> : documents.length === 0 ? (
        <EmptyState title="Your library is empty">Choose one or more PDFs above to get started.</EmptyState>
      ) : (
        <>
          {deleteError && <div className="mb-3"><ErrorNotice>{deleteError}</ErrorNotice></div>}
          <div className="panel overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <caption className="sr-only">Uploaded documents</caption>
              <thead className="border-b border-line bg-page text-ink-soft">
                <tr><th className="p-3 font-medium">Document</th><th className="p-3 font-medium">Status</th><th className="p-3 font-medium">Pages</th><th className="p-3 font-medium">Chunks</th><th className="p-3 font-medium">Uploaded</th><th className="p-3"><span className="sr-only">Actions</span></th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {documents.map((d) => (
                  <Fragment key={d.id}>
                    <tr>
                      <td className="p-3">
                        <button className="flex items-center gap-1 text-left font-medium" aria-expanded={expanded === d.id} onClick={() => setExpanded(expanded === d.id ? null : d.id)}>
                          {expanded === d.id ? <ChevronDown className="h-4 w-4" aria-hidden /> : <ChevronRight className="h-4 w-4" aria-hidden />}
                          <span className="break-all">{d.filename}</span>
                        </button>
                      </td>
                      <td className="p-3"><StatusBadge status={d.status} /></td>
                      <td className="p-3 tabular-nums">{d.page_count}</td>
                      <td className="p-3 tabular-nums">{d.chunk_count}</td>
                      <td className="p-3 text-ink-soft">{formatDate(d.uploaded_at)}</td>
                      <td className="p-3 text-right">
                        {confirmId === d.id ? (
                          <span className="inline-flex gap-2">
                            <button className="btn-danger" onClick={() => void remove(d.id)}>Confirm delete</button>
                            <button className="btn-quiet" onClick={() => setConfirmId(null)}>Cancel</button>
                          </span>
                        ) : (
                          <button className="btn-quiet" aria-label={`Delete ${d.filename}`} onClick={() => setConfirmId(d.id)}><Trash2 className="h-4 w-4" aria-hidden /> Delete</button>
                        )}
                      </td>
                    </tr>
                    {expanded === d.id && (
                      <tr className="bg-page">
                        <td colSpan={6} className="p-4">
                          <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
                            <div><dt className="text-ink-faint">Document ID</dt><dd className="break-all font-mono text-xs">{d.id}</dd></div>
                            <div><dt className="text-ink-faint">File hash (SHA-256)</dt><dd className="break-all font-mono text-xs">{d.file_hash}</dd></div>
                            <div><dt className="text-ink-faint">Size</dt><dd>{formatBytes(d.size_bytes)}</dd></div>
                            <div><dt className="text-ink-faint">Characters extracted</dt><dd>{d.char_count.toLocaleString()}</dd></div>
                            <div><dt className="text-ink-faint">Embedding model</dt><dd>{d.embedding_model ?? "none"}</dd></div>
                          </dl>
                          {d.error_message && <div className="mt-3"><ErrorNotice>{d.error_message}</ErrorNotice></div>}
                          {d.status === "Ready" && <p className="mt-3 text-sm"><Link className="font-medium text-signal underline" to={`/search?doc=${d.id}`}>Search this document</Link></p>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
