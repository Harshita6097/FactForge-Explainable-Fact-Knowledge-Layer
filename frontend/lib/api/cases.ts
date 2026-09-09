import apiClient from "./client";

export interface CaseRelationship {
  id: string;
  relationship_type: string;
  explanation: string | null;
  reasoning_summary: string | null;
  confidence: number;
  source_fact: any | null;
  target_fact: any | null;
  reasoning_steps: Array<{ step: number; check: string; result: string; detail: string }>;
}

export interface ExtractionFailureCase {
  id: string;
  document_id: string;
  original_filename: string;
  page_number: number | null;
  raw_text: string;
  failure_reason: string;
  chain_of_thought: string;
  confidence: number;
  created_at: string;
}

export interface CasesResponse {
  corroborated: CaseRelationship | null;
  contradiction: CaseRelationship | null;
  reconciled: CaseRelationship | null;
  extraction_failure: ExtractionFailureCase | null;
}

export async function fetchCases(project_id?: string): Promise<CasesResponse> {
  const { data } = await apiClient.get("/api/cases", {
    params: project_id ? { project_id } : undefined,
  });
  return data;
}
