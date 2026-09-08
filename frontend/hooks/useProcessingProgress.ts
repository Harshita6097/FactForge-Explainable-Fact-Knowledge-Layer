import { useEffect, useState, useRef } from "react";

export interface ProcessingProgress {
  status: string;
  page_count: number;
  processed_pages: number;
  facts_found: number;
  relationships_found: number;
  stage: string;
  pct: number;
  done?: boolean;
  timeout?: boolean;
  error?: string;
}

export function useProcessingProgress(docId: string | null, enabled = true) {
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [isDone, setIsDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!docId || !enabled || isDone) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const es = new EventSource(`${apiUrl}/api/documents/${docId}/progress`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: ProcessingProgress = JSON.parse(e.data);
        setProgress(data);
        if (data.done || data.timeout || data.error) {
          setIsDone(true);
          es.close();
        }
      } catch {}
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [docId, enabled, isDone]);

  const reset = () => {
    setProgress(null);
    setIsDone(false);
  };

  return { progress, isDone, reset };
}
