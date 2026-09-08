import apiClient from "./client";
import { CanonicalFact } from "@/types";

export async function fetchCanonicalFacts(params?: {
  entity?: string;
  attribute?: string;
  period?: string;
  limit?: number;
  offset?: number;
}): Promise<CanonicalFact[]> {
  const { data } = await apiClient.get("/api/knowledge/facts", { params });
  return data;
}

export async function fetchCanonicalFact(id: string): Promise<CanonicalFact> {
  const { data } = await apiClient.get(`/api/knowledge/facts/${id}`);
  return data;
}

export async function fetchKnowledgeStats(): Promise<{
  canonical_facts: number;
  multi_document_facts: number;
  conflicted_facts: number;
  unique_entities: number;
  unique_attributes: number;
}> {
  const { data } = await apiClient.get("/api/knowledge/stats");
  return data;
}

export async function fetchEntities(): Promise<{
  entity: string;
  fact_count: number;
  avg_confidence: number;
  period_count: number;
}[]> {
  const { data } = await apiClient.get("/api/knowledge/entities");
  return data;
}

export async function fetchEntityFacts(entity: string): Promise<CanonicalFact[]> {
  const { data } = await apiClient.get(`/api/knowledge/entities/${encodeURIComponent(entity)}/facts`);
  return data;
}
