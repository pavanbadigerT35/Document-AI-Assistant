import { useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import type { DocumentInfo } from "../types";
import { docColor } from "../lib";

interface Props { documents: DocumentInfo[]; value: string[]; onChange: (ids: string[]) => void; id?: string }

/** Empty selection means "all documents". */
export function ScopeSelector({ documents, value, onChange, id = "scope" }: Props) {
  const details = useRef<HTMLDetailsElement>(null);
  const label = value.length === 0 ? "All documents" : value.length === 1 ? documents.find((d) => d.id === value[0])?.filename ?? "1 document" : `${value.length} documents`;
  const toggle = (docId: string) => onChange(value.includes(docId) ? value.filter((v) => v !== docId) : [...value, docId]);

  useEffect(() => {
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (event.target instanceof Node && !details.current?.contains(event.target)) {
        details.current?.removeAttribute("open");
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") details.current?.removeAttribute("open");
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  if (documents.length === 0) return <span className="text-sm text-ink-soft">No indexed documents yet</span>;
  return (
    <details className="relative" id={id} ref={details}>
      <summary className="btn-quiet cursor-pointer list-none" aria-label={`Search scope: ${label}`}>
        <span className="max-w-[16rem] truncate">{label}</span>
        <ChevronDown className="h-4 w-4" aria-hidden />
      </summary>
      <fieldset className="panel absolute z-10 mt-1 min-w-64 max-w-sm p-2 shadow-lg">
        <legend className="sr-only">Choose documents</legend>
        <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-page">
          <input type="checkbox" checked={value.length === 0} onChange={() => onChange([])} /> All documents
        </label>
        {documents.map((d) => (
          <label key={d.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-page">
            <input type="checkbox" checked={value.includes(d.id)} onChange={() => toggle(d.id)} />
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: docColor(d.id) }} aria-hidden />
            <span className="break-all">{d.filename}</span>
          </label>
        ))}
      </fieldset>
    </details>
  );
}
