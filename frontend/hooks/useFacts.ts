import { useQuery } from "@tanstack/react-query";
import { fetchFacts, fetchFact, fetchFactStats, fetchDocumentFacts } from "@/lib/api/facts";

export function useFacts(params?: { document_id?: string; entity?: string; attribute?: string }) {
  return useQuery({
    queryKey: ["facts", params],
    queryFn: () => fetchFacts(params),
  });
}

export function useFact(id: string) {
  return useQuery({
    queryKey: ["facts", id],
    queryFn: () => fetchFact(id),
    enabled: !!id,
  });
}

export function useFactStats() {
  return useQuery({
    queryKey: ["facts", "stats"],
    queryFn: fetchFactStats,
    refetchInterval: 10_000,
  });
}

export function useDocumentFacts(docId: string) {
  return useQuery({
    queryKey: ["facts", "document", docId],
    queryFn: () => fetchDocumentFacts(docId),
    enabled: !!docId,
  });
}
