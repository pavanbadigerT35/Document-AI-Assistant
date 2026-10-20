import { useEffect, useState } from "react";

const SCOPE_PREFERENCE_KEY = "document-scope-preference-v1";

function readPreference(): string[] {
  const saved = localStorage.getItem(SCOPE_PREFERENCE_KEY);
  if (!saved) return [];
  try {
    const value: unknown = JSON.parse(saved);
    return Array.isArray(value) && value.every((id) => typeof id === "string") ? value : [];
  } catch {
    return [];
  }
}

export function useDocumentScope(initialScope?: string[]) {
  const [scope, setScope] = useState<string[]>(() => initialScope ?? readPreference());

  useEffect(() => {
    localStorage.setItem(SCOPE_PREFERENCE_KEY, JSON.stringify(scope));
  }, [scope]);

  return [scope, setScope] as const;
}
