import { Search as SearchIcon } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { ScopeSelector } from "../components/ScopeSelector";
import { SourceCard } from "../components/SourceCard";
import { EmptyState, ErrorNotice, PageHeader, Spinner } from "../components/ui";
import { useDocuments } from "../hooks/useDocuments";
import { useDocumentScope } from "../hooks/useDocumentScope";
import { errorMessage } from "../lib";
import type { SearchResponse } from "../types";

export default function SearchPage() {
  const [params] = useSearchParams();
  const { ready, loading: docsLoading } = useDocuments();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [scope, setScope] = useDocumentScope(params.get("doc") ? [params.get("doc")!] : undefined);
  const [topK, setTopK] = useState(5);
  const [lastQuery, setLastQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoRan = useRef(false);

  async function run(q: string, s = scope, k = topK) {
    if (!q.trim()) return;
    setLoading(true); setError(null);
    try { setResponse(await api.search(q.trim(), s, k)); setLastQuery(q.trim()); }
    catch (e) { setError(errorMessage(e)); setResponse(null); }
    finally { setLoading(false); }
  }

  useEffect(() => {  // arriving from the Topic Explorer with ?q=...
    if (!autoRan.current && params.get("q")) { autoRan.current = true; void run(params.get("q")!); }
  }); // eslint-disable-line

  const onSubmit = (e: FormEvent) => { e.preventDefault(); void run(query); };

  return (
    <>
      <PageHeader title="Knowledge search">Find passages by meaning, not just exact words. This works without any chat model.</PageHeader>
      <form onSubmit={onSubmit} className="mb-6 space-y-3" role="search">
        <div className="flex gap-2">
          <input className="field" aria-label="Search query" placeholder="e.g. how is time saved calculated?" value={query} onChange={(e) => setQuery(e.target.value)} maxLength={1000} />
          <button className="btn-primary" type="submit" disabled={loading || !query.trim()}><SearchIcon className="h-4 w-4" aria-hidden /> Search</button>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <ScopeSelector documents={ready} value={scope} onChange={setScope} />
          <label className="flex items-center gap-2 text-ink-soft">Results
            <select className="field !w-auto" value={topK} onChange={(e) => setTopK(Number(e.target.value))}>{[3, 5, 10].map((n) => <option key={n}>{n}</option>)}</select>
          </label>
        </div>
      </form>

      {!docsLoading && ready.length === 0 && <EmptyState title="Nothing to search yet">Upload and index a PDF in the document library first.</EmptyState>}
      {loading && <Spinner label="Searching…" />}
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {response && !loading && (
        response.results.length === 0 ? (
          <EmptyState title="No matching passages">
            Nothing scored above the similarity threshold ({response.retrieval.min_score}).
            {response.retrieval.top_score !== null && ` The closest passage scored ${response.retrieval.top_score.toFixed(2)}.`} Try different words or widen the scope.
          </EmptyState>
        ) : (
          <section aria-label="Search results">
            <p className="mb-3 text-sm text-ink-soft">{response.results.length} passage(s) in {response.retrieval.latency_ms} ms</p>
            <ol className="space-y-3">
              {response.results.map((r) => (
                <li key={r.chunk_id}><SourceCard documentId={r.document_id} filename={r.filename} page={r.page} text={r.text} score={r.score} query={lastQuery} /></li>
              ))}
            </ol>
          </section>
        )
      )}
    </>
  );
}
