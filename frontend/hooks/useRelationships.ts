import { useQuery } from "@tanstack/react-query";
import {
  fetchRelationships,
  fetchRelationship,
  fetchRelationshipsSummary,
  fetchFactRelationships,
  fetchExtractionFailures,
} from "@/lib/api/relationships";

export function useRelationships(params?: { relationship_type?: string; project_id?: string; limit?: number }) {
  return useQuery({
    queryKey: ["relationships", params],
    queryFn: () => fetchRelationships(params),
  });
}

export function useRelationship(id: string) {
  return useQuery({
    queryKey: ["relationships", id],
    queryFn: () => fetchRelationship(id),
    enabled: !!id,
  });
}

export function useRelationshipsSummary(params?: { project_id?: string }) {
  return useQuery({
    queryKey: ["relationships", "summary", params],
    queryFn: () => fetchRelationshipsSummary(params),
    refetchInterval: 15_000,
  });
}

export function useFactRelationships(factId: string) {
  return useQuery({
    queryKey: ["relationships", "fact", factId],
    queryFn: () => fetchFactRelationships(factId),
    enabled: !!factId,
  });
}

export function useExtractionFailures(params?: { project_id?: string; document_id?: string; limit?: number }) {
  return useQuery({
    queryKey: ["extraction-failures", params],
    queryFn: () => fetchExtractionFailures(params),
  });
}
