import { AlertCircle, CheckCircle2, Info, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import type { DocStatus } from "../types";

const STATUS_STYLE: Record<DocStatus, string> = {
  Ready: "bg-green-50 text-pass border-green-200",
  Processing: "bg-blue-50 text-work border-blue-200",
  Pending: "bg-slate-100 text-ink-soft border-line",
  Failed: "bg-red-50 text-fail border-red-200",
};

export function StatusBadge({ status }: { status: DocStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}>
      {status === "Processing" && <Loader2 className="h-3 w-3 animate-spin" aria-hidden />}
      {status}
    </span>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-2 text-sm text-ink-soft">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
    </div>
  );
}

export function ErrorNotice({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-fail">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1">{children}</div>
      {onRetry && <button className="font-medium underline" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "success" | "warn"; children: ReactNode }) {
  const style = { info: "border-blue-200 bg-pale-blue text-work", success: "border-green-200 bg-pale-green text-pass", warn: "border-amber-300 bg-amber-50 text-amber-900" }[tone];
  const Icon = tone === "success" ? CheckCircle2 : Info;
  return (
    <div role="status" className={`flex items-start gap-2 rounded-lg border p-4 text-sm ${style}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-soft-stone/50 px-6 py-14 text-center">
      <h2 className="text-2xl">{title}</h2>
      {children && <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-soft">{children}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-8 border-b border-line pb-6">
      <p className="eyebrow mb-3">Document learning assistant</p>
      <h1 className="text-4xl sm:text-5xl">{title}</h1>
      {children && <p className="mt-3 max-w-2xl text-base leading-7 text-ink-soft">{children}</p>}
    </header>
  );
}
