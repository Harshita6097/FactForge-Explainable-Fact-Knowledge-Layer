import apiClient from "./client";
import { Relationship } from "@/types";

export async function fetchRelationships(params?: {
  relationship_type?: string;
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

export async function fetchRelationshipsSummary(): Promise<Record<string, number>> {
  const { data } = await apiClient.get("/api/relationships/summary");
  return data;
}

export async function fetchFactRelationships(factId: string): Promise<Relationship[]> {
  const { data } = await apiClient.get(`/api/facts/${factId}/relationships`);
  return data;
}

export async function triggerAnalysis(docId: string): Promise<void> {
  await apiClient.post(`/api/documents/${docId}/analyze`);
}
