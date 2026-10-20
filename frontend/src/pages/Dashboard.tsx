import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, Notice, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { errorMessage, formatDate } from "../lib";
import type { Stats } from "../types";

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api.stats().then((s) => { setStats(s); setError(null); }).catch((e) => setError(errorMessage(e))); }, []);
  useEffect(load, [load]);

  if (error) return <><PageHeader title="Dashboard" /><ErrorNotice onRetry={load}>{error}</ErrorNotice></>;
  if (!stats) return <><PageHeader title="Dashboard" /><Spinner label="Loading statistics…" /></>;

  const ledger = [
    ["Documents uploaded", stats.total_documents],
    ["Indexed and searchable", stats.ready_documents],
    ["Pages indexed", stats.total_pages],
    ["Passages (chunks)", stats.total_chunks],
  ] as const;

  return (
    <>
      <PageHeader title="Dashboard">Your personal learning space, built from the documents you trust.</PageHeader>
      {!stats.llm_configured && (
        <div className="mb-6"><Notice tone="warn">Chat and quiz generation are off because no Groq API key is set. Upload and search still work. Add <code>GROQ_API_KEY</code> to <code>backend/.env</code> and restart the backend.</Notice></div>
      )}
      <dl className="mb-10 grid grid-cols-2 border-y border-line md:grid-cols-4 md:divide-x md:divide-line">
        {ledger.map(([label, value]) => (
          <div key={label} className="border-b border-line px-4 py-5 last:border-b-0 even:border-l md:border-b-0 md:px-6 md:py-6">
            <dd className="font-serif text-4xl tabular-nums sm:text-5xl">{value}</dd>
            <dt className="mt-2 max-w-32 text-sm leading-5 text-ink-soft">{label}</dt>
          </div>
        ))}
      </dl>
      {stats.failed_documents > 0 && <div className="mb-6"><ErrorNotice>{stats.failed_documents} document(s) failed to index. Open the <Link className="underline" to="/library">library</Link> for details.</ErrorNotice></div>}

      {stats.total_documents === 0 ? (
        <EmptyState title="No documents yet" action={<Link to="/library" className="btn-primary">Upload your first PDF</Link>}>
          Upload a syllabus, training notes or documentation to start searching and asking questions.
        </EmptyState>
      ) : (
        <div className="grid gap-10 lg:grid-cols-2">
          <section aria-labelledby="recent-docs">
            <div className="mb-4 flex items-baseline justify-between border-b border-line pb-3">
              <h2 id="recent-docs" className="text-2xl">Recent documents</h2>
              <Link className="text-sm text-ink-soft underline underline-offset-4 hover:text-ink" to="/library">View library</Link>
            </div>
            <ul className="divide-y divide-line border-b border-line">
              {stats.recent_documents.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 py-4 text-sm">
                  <span className="break-all font-medium">{d.filename}</span><StatusBadge status={d.status} />
                </li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="recent-activity">
            <div className="mb-4 flex items-baseline justify-between border-b border-line pb-3">
              <h2 id="recent-activity" className="text-2xl">Recent activity</h2>
              <span className="eyebrow">Latest updates</span>
            </div>
            <ul className="divide-y divide-line border-b border-line">
              {stats.recent_activity.map((a, i) => (
                <li key={i} className="py-4 text-sm"><p>{a.message}</p><p className="mt-1 text-xs text-ink-faint">{formatDate(a.timestamp)}</p></li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </>
  );
}
