import { Send, Trash2 } from "lucide-react";
import { FormEvent, Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { ScopeSelector } from "../components/ScopeSelector";
import { SourceCard } from "../components/SourceCard";
import { ErrorNotice, Notice, PageHeader, Spinner } from "../components/ui";
import { useDocuments } from "../hooks/useDocuments";
import { useDocumentScope } from "../hooks/useDocumentScope";
import { errorMessage, newId } from "../lib";
import type { ChatResponse, Suggestion } from "../types";

interface Message { id: string; role: "user" | "assistant"; text: string; response?: ChatResponse; error?: string; question?: string }
const STORE = "chat-history-v1";

function AnswerText({ msgId, response }: { msgId: string; response: ChatResponse }) {
  const known = new Set(response.sources.map((s) => s.source_id));
  return (
    <p className="whitespace-pre-line font-serif text-[16px] leading-relaxed">
      {response.answer.split(/(\[S\d+\])/g).map((part, i) => {
        const m = part.match(/^\[(S\d+)\]$/);
        if (!m) return <Fragment key={i}>{part}</Fragment>;
        return known.has(m[1]) ? <a key={i} href={`#${msgId}-${m[1]}`} className="mx-0.5 rounded bg-signal-tint px-1 text-xs font-semibold text-signal-dark no-underline">{m[1]}</a> : null;
      })}
    </p>
  );
}

export default function Chat() {
  const { ready } = useDocuments();
  const [scope, setScope] = useDocumentScope();
  const [messages, setMessages] = useState<Message[]>(() => { try { return JSON.parse(sessionStorage.getItem(STORE) ?? "[]"); } catch { return []; } });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { sessionStorage.setItem(STORE, JSON.stringify(messages)); end.current?.scrollIntoView?.({ block: "end" }); }, [messages]);
  useEffect(() => { if (ready.length) api.suggestions(scope).then(setSuggestions).catch(() => setSuggestions([])); }, [ready.length, scope]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || loading) return;
    const uid = newId();
    setMessages((m) => [...m, { id: uid, role: "user", text: q }]);
    setInput(""); setLoading(true);
    const aid = newId();
    try {
      const response = await api.chat(q, scope);
      setMessages((m) => [...m, { id: aid, role: "assistant", text: response.answer, response, question: q }]);
    } catch (e) {
      setMessages((m) => [...m, { id: aid, role: "assistant", text: "", error: errorMessage(e), question: q }]);
    } finally { setLoading(false); }
  }

  const onSubmit = (e: FormEvent) => { e.preventDefault(); void ask(input); };

  return (
    <>
      <PageHeader title="AI chat">Answers come only from your documents, with the passages they rely on shown underneath.</PageHeader>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ScopeSelector documents={ready} value={scope} onChange={setScope} />
        {messages.length > 0 && <button className="btn-quiet" onClick={() => setMessages([])}><Trash2 className="h-4 w-4" aria-hidden /> Clear conversation</button>}
      </div>

      <section aria-label="Conversation" aria-live="polite" className="mb-4 space-y-5">
        {messages.length === 0 && ready.length > 0 && suggestions.length > 0 && (
          <div>
            <p className="mb-2 text-sm text-ink-soft">Try a question based on headings found in your documents:</p>
            <ul className="flex flex-wrap gap-2">
              {suggestions.map((s) => <li key={s.question}><button className="btn-quiet text-left" onClick={() => void ask(s.question)}>{s.question}</button></li>)}
            </ul>
          </div>
        )}
        {messages.length === 0 && ready.length === 0 && <Notice>Upload and index a PDF in the document library before asking questions.</Notice>}
        {messages.map((m) => m.role === "user" ? (
          <div key={m.id} className="ml-auto max-w-[85%] rounded-md bg-rail px-4 py-2.5 text-white">{m.text}</div>
        ) : (
          <div key={m.id} className="space-y-3">
            {m.error ? (
              <ErrorNotice onRetry={m.question ? () => void ask(m.question!) : undefined}>{m.error}</ErrorNotice>
            ) : m.response && (
              <>
                {m.response.insufficient_evidence ? (
                  <Notice tone="warn"><strong>Not enough evidence.</strong> {m.response.answer} Try rephrasing, or select a different document.</Notice>
                ) : (
                  <div className="panel p-4"><AnswerText msgId={m.id} response={m.response} /></div>
                )}
                {m.response.warning && <Notice tone="warn">{m.response.warning}</Notice>}
                {m.response.sources.length > 0 && (
                  <div>
                    <h2 className="mb-2 text-base font-semibold">Sources</h2>
                    <ul className="space-y-2">
                      {m.response.sources.map((s) => (
                        <li key={s.source_id}><SourceCard id={`${m.id}-${s.source_id}`} label={s.source_id} documentId={s.document_id} filename={s.filename} page={s.page} text={s.excerpt} score={s.score} /></li>
                      ))}
                    </ul>
                  </div>
                )}
                <details className="text-xs text-ink-faint">
                  <summary className="cursor-pointer">Retrieval details</summary>
                  <p className="mt-1">Top similarity {m.response.retrieval.top_score ?? "n/a"} · {m.response.retrieval.above_threshold} of {m.response.retrieval.candidates} passages above threshold {m.response.retrieval.min_score} · {m.response.retrieval.latency_ms} ms{m.response.llm ? ` · ${m.response.llm.provider}/${m.response.llm.model}` : ""}{m.response.request_id ? ` · request ${m.response.request_id}` : ""}</p>
                </details>
              </>
            )}
          </div>
        ))}
        {loading && <Spinner label="Searching your documents and writing an answer…" />}
        <div ref={end} />
      </section>

      <form onSubmit={onSubmit} className="sticky bottom-0 flex gap-2 bg-page py-3">
        <input className="field" aria-label="Your question" placeholder="Ask about your documents…" value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} disabled={loading || ready.length === 0} />
        <button className="btn-primary" type="submit" disabled={loading || !input.trim() || ready.length === 0}><Send className="h-4 w-4" aria-hidden /> Ask</button>
      </form>
    </>
  );
}
