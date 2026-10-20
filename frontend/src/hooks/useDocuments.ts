import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { DocumentInfo } from "../types";

/** Loads the document list and keeps refreshing while any document is still being processed. */
export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await api.documents());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!documents.some((d) => d.status === "Pending" || d.status === "Processing")) return;
    const t = setInterval(() => void refresh(), 2000);
    return () => clearInterval(t);
  }, [documents, refresh]);

  return { documents, loading, error, refresh, ready: documents.filter((d) => d.status === "Ready") };
}
