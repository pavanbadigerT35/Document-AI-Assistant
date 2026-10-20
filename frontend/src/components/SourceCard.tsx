import { useState } from "react";
import { docColor, queryTerms } from "../lib";

function Highlighted({ text, query }: { text: string; query?: string }) {
  const terms = query ? queryTerms(query) : [];
  if (!terms.length) return <>{text}</>;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return (
    <>
      {text.split(re).map((part, i) =>
        terms.includes(part.toLowerCase()) ? <mark key={i} className="rounded-sm bg-mark px-0.5">{part}</mark> : <span key={i}>{part}</span>,
      )}
    </>
  );
}

interface Props { id?: string; label?: string; documentId: string; filename: string; page: number; text: string; score?: number; query?: string }

export function SourceCard({ id, label, documentId, filename, page, text, score, query }: Props) {
  const [open, setOpen] = useState(false);
  const long = text.length > 420;
  const shown = long && !open ? text.slice(0, 420).trimEnd() + "…" : text;
  return (
    <article id={id} className="panel flex scroll-mt-4 overflow-hidden" aria-label={`Source: ${filename}, page ${page}`}>
      <div className="w-1.5 shrink-0" style={{ background: docColor(documentId) }} aria-hidden />
      <div className="min-w-0 flex-1 p-4">
        <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {label && <span className="rounded bg-signal-tint px-1.5 py-0.5 text-xs font-semibold text-signal-dark">{label}</span>}
          <span className="break-all font-medium">{filename}</span>
          <span className="rounded border border-line px-1.5 text-sm text-ink-soft">page {page}</span>
          {score !== undefined && <span className="ml-auto text-xs text-ink-faint">similarity {score.toFixed(2)}</span>}
        </header>
        <p className="mt-2 whitespace-pre-line font-serif text-[15px] leading-relaxed text-ink">
          <Highlighted text={shown} query={query} />
        </p>
        {long && (
          <button className="mt-1 text-sm font-medium text-signal underline" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? "Show less" : "Show full excerpt"}
          </button>
        )}
      </div>
    </article>
  );
}
