export function docColor(id: string): string {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 50% 40%)`;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Words from the query worth highlighting in an excerpt (4+ letters). */
export function queryTerms(query: string): string[] {
  return Array.from(new Set(query.toLowerCase().match(/[a-z0-9]{4,}/g) ?? []));
}

export function errorMessage(e: unknown, fallback = "Something went wrong."): string {
  return e instanceof Error ? e.message : fallback;
}

/** crypto.randomUUID only exists in secure contexts (https or localhost); fall back so LAN/IP access still works. */
export function newId(source: { randomUUID?: () => string } | undefined = globalThis.crypto): string {
  return typeof source?.randomUUID === "function" ? source.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
