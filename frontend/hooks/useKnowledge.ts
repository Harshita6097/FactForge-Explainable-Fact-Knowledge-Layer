import { useQuery } from "@tanstack/react-query";
import {
  fetchCanonicalFacts,
  fetchCanonicalFact,
  fetchKnowledgeStats,
  fetchEntities,
} from "@/lib/api/knowledge";

export function useCanonicalFacts(params?: {
  entity?: string;
  attribute?: string;
  period?: string;
}) {
  return useQuery({
    queryKey: ["canonical-facts", params],
    queryFn: () => fetchCanonicalFacts(params),
  });
}

export function useCanonicalFact(id: string) {
  return useQuery({
    queryKey: ["canonical-facts", id],
    queryFn: () => fetchCanonicalFact(id),
    enabled: !!id,
  });
}

export function useKnowledgeStats() {
  return useQuery({
    queryKey: ["knowledge", "stats"],
    queryFn: fetchKnowledgeStats,
    refetchInterval: 15_000,
  });
}

export function useEntities() {
  return useQuery({
    queryKey: ["knowledge", "entities"],
    queryFn: fetchEntities,
  });
}
