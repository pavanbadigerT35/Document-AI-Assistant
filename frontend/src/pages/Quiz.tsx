import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { ScopeSelector } from "../components/ScopeSelector";
import { ErrorNotice, Notice, PageHeader, Spinner } from "../components/ui";
import { useDocuments } from "../hooks/useDocuments";
import { useDocumentScope } from "../hooks/useDocumentScope";
import { errorMessage } from "../lib";
import type { QuizHealth, QuizQuestion, QuizResponse } from "../types";

function Question({ q, index }: { q: QuizQuestion; index: number }) {
  const [picked, setPicked] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(false);
  const name = `q${index}`;
  return (
    <li className="panel p-4">
      <p className="font-serif text-lg font-medium">{index + 1}. {q.question}</p>
      {q.options.length > 0 && (
        <fieldset className="mt-3 space-y-1.5">
          <legend className="sr-only">Options for question {index + 1}</legend>
          {q.options.map((o, i) => {
            const right = revealed && i === q.correct_index;
            const wrong = revealed && picked === i && i !== q.correct_index;
            return (
              <label key={i} className={`flex cursor-pointer items-start gap-2 rounded border px-3 py-2 text-sm ${right ? "border-pass bg-green-50" : wrong ? "border-fail bg-red-50" : "border-line"}`}>
                <input type="radio" name={name} checked={picked === i} onChange={() => setPicked(i)} className="mt-1" /> <span>{o}{right && <strong className="ml-2 text-pass">Correct answer</strong>}</span>
              </label>
            );
          })}
        </fieldset>
      )}
      <button className="btn-quiet mt-3" onClick={() => setRevealed(!revealed)} aria-expanded={revealed}>{revealed ? "Hide answer" : "Reveal answer"}</button>
      {revealed && (
        <div className="mt-3 rounded bg-page p-3 text-sm">
          {q.answer && <p><strong>Answer:</strong> {q.answer}</p>}
          {q.explanation && <p><strong>Why:</strong> {q.explanation}</p>}
          <p className="mt-1 text-ink-soft">Source: {q.source.filename}, page {q.source.page}</p>
        </div>
      )}
    </li>
  );
}

export default function Quiz() {
  const [params] = useSearchParams();
  const { ready } = useDocuments();
  const [health, setHealth] = useState<QuizHealth | null>(null);
  const [scope, setScope] = useDocumentScope(params.get("doc") ? [params.get("doc")!] : undefined);
  const [topic, setTopic] = useState(params.get("topic") ?? "");
  const [count, setCount] = useState(5);
  const [kind, setKind] = useState<"mcq" | "short_answer">("mcq");
  const [quiz, setQuiz] = useState<QuizResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.quizHealth().then(setHealth).catch((e) => setHealth({ available: false, reason: errorMessage(e) })); }, []);

  async function generate() {
    setLoading(true); setError(null); setQuiz(null);
    try { setQuiz(await api.generateQuiz(scope, topic, count, kind)); }
    catch (e) { setError(errorMessage(e)); }
    finally { setLoading(false); }
  }

  const disabledReason = health && !health.available ? health.reason : ready.length === 0 ? "Index a document first." : null;

  return (
    <>
      <PageHeader title="Quiz and revision">Practice questions written from passages in your documents. Leave the topic empty to cover the whole selection.</PageHeader>
      {disabledReason && <div className="mb-4"><Notice tone="warn">{disabledReason}</Notice></div>}
      <div className="panel mb-6 grid gap-4 p-4 md:grid-cols-2">
        <div><span className="mb-1 block text-sm font-medium">Documents</span><ScopeSelector documents={ready} value={scope} onChange={setScope} /></div>
        <label className="block text-sm font-medium">Topic (optional)
          <input className="field mt-1 font-normal" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. self-healing automation" maxLength={300} />
        </label>
        <label className="block text-sm font-medium">Number of questions
          <select className="field mt-1 font-normal" value={count} onChange={(e) => setCount(Number(e.target.value))}>{[3, 5, 8, 10].map((n) => <option key={n}>{n}</option>)}</select>
        </label>
        <label className="block text-sm font-medium">Question type
          <select className="field mt-1 font-normal" value={kind} onChange={(e) => setKind(e.target.value as "mcq" | "short_answer")}>
            <option value="mcq">Multiple choice</option><option value="short_answer">Descriptive answer</option>
          </select>
        </label>
        <div className="md:col-span-2"><button className="btn-primary" onClick={() => void generate()} disabled={loading || !!disabledReason}>Generate questions</button></div>
      </div>
      {loading && <Spinner label="Reading the source passages and writing questions…" />}
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {quiz && (
        <section aria-label="Generated questions">
          <div className="mb-4"><Notice>{quiz.label}</Notice></div>
          <ol className="space-y-4">{quiz.questions.map((q, i) => <Question key={i} q={q} index={i} />)}</ol>
        </section>
      )}
    </>
  );
}
