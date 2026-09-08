import { useQuery } from "@tanstack/react-query";
import {
  fetchRelationships,
  fetchRelationship,
  fetchRelationshipsSummary,
  fetchFactRelationships,
} from "@/lib/api/relationships";

export function useRelationships(params?: { relationship_type?: string; limit?: number }) {
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

export function useRelationshipsSummary() {
  return useQuery({
    queryKey: ["relationships", "summary"],
    queryFn: fetchRelationshipsSummary,
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
