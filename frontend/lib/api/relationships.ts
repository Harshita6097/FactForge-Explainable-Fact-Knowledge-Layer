import apiClient from "./client";
import { Relationship, ExtractionFailure } from "@/types";

export async function fetchRelationships(params?: {
  relationship_type?: string;
  project_id?: string;
  limit?: number;
  offset?: number;
}): Promise<Relationship[]> {
  const { data } = await apiClient.get("/api/relationships", { params });
  return data;
}

export async function fetchRelationship(id: string): Promise<Relationship> {
  const { data } = await apiClient.get(`/api/relationships/${id}`);
  return data;
}

export async function fetchRelationshipsSummary(params?: { project_id?: string }): Promise<Record<string, number>> {
  const { data } = await apiClient.get("/api/relationships/summary", { params });
  return data;
}

export async function fetchFactRelationships(factId: string): Promise<Relationship[]> {
  const { data } = await apiClient.get(`/api/facts/${factId}/relationships`);
  return data;
}

export async function fetchExtractionFailures(params?: {
  project_id?: string;
  document_id?: string;
  limit?: number;
}): Promise<ExtractionFailure[]> {
  const { data } = await apiClient.get("/api/extraction-failures", { params });
  return data;
}

export async function triggerAnalysis(docId: string): Promise<void> {
  await apiClient.post(`/api/documents/${docId}/analyze`);
}
