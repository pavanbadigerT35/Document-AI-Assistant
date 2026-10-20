import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, Notice, PageHeader, Spinner } from "../components/ui";
import { docColor, errorMessage } from "../lib";
import type { TopicsResponse } from "../types";

export default function Topics() {
  const [data, setData] = useState<TopicsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.topics().then(setData).catch((e) => setError(errorMessage(e))); }, []);

  return (
    <>
      <PageHeader title="Topic explorer">Headings found in your documents. Select one to search for its passages, or choose Quiz me to practise it.</PageHeader>
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {!data && !error && <Spinner label="Loading topics…" />}
      {data && (
        <>
          <div className="mb-6"><Notice>{data.note}</Notice></div>
          {data.documents.length === 0 ? (
            <EmptyState title="No topics yet" action={<Link className="btn-primary" to="/library">Go to library</Link>}>Index a document to see its headings here.</EmptyState>
          ) : (
            <div className="space-y-8">
              {data.documents.map((d) => (
                <section key={d.document_id} aria-labelledby={`t-${d.document_id}`}>
                  <h2 id={`t-${d.document_id}`} className="mb-2 flex items-center gap-2 text-xl font-semibold">
                    <span className="h-3 w-3 rounded-full" style={{ background: docColor(d.document_id) }} aria-hidden /> <span className="break-all">{d.filename}</span>
                  </h2>
                  {d.topics.length === 0 ? <p className="text-sm text-ink-soft">No headings were detected in this document.</p> : (
                    <ul className="panel divide-y divide-line">
                      {d.topics.map((t, i) => (
                        <li key={i} className="flex items-stretch" style={{ paddingLeft: `${(t.level - 1) * 1.25}rem` }}>
                          <Link className="flex min-w-0 flex-1 items-baseline justify-between gap-3 px-3 py-2 text-sm hover:bg-page" to={`/search?q=${encodeURIComponent(t.title)}&doc=${d.document_id}`}>
                            <span className={t.level === 1 ? "font-semibold" : ""}>{t.title}</span>
                            <span className="shrink-0 text-xs text-ink-faint">page {t.page}</span>
                          </Link>
                          <Link className="shrink-0 px-3 py-2 text-xs font-medium text-signal underline hover:bg-page" aria-label={`Quiz me on ${t.title}`} to={`/quiz?topic=${encodeURIComponent(t.title)}&doc=${d.document_id}`}>
                            Quiz me
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
