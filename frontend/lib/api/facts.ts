import apiClient from "./client";
import { Fact, DashboardStats } from "@/types";

export async function fetchFacts(params?: {
  document_id?: string;
  project_id?: string;
  entity?: string;
  attribute?: string;
  limit?: number;
  offset?: number;
}): Promise<Fact[]> {
  const { data } = await apiClient.get("/api/facts", { params });
  return data;
}

export async function fetchFact(id: string): Promise<Fact> {
  const { data } = await apiClient.get(`/api/facts/${id}`);
  return data;
}

export async function fetchFactStats(): Promise<DashboardStats> {
  const { data } = await apiClient.get("/api/facts/stats");
  return data;
}

export async function fetchDocumentFacts(docId: string): Promise<Fact[]> {
  const { data } = await apiClient.get(`/api/documents/${docId}/facts`);
  return data;
}
