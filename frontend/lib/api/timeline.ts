import apiClient from "./client";

export interface TimelineFact {
  id: string;
  entity: string;
  attribute: string;
  canonical_value: string | null;
  raw_value: string;
  unit: string | null;
  confidence: number;
  document: string;
  page_number: number | null;
  snippet: string | null;
  relationships: string[];
}

export interface TimelineEntry {
  period: string;
  period_type: "quarter" | "fiscal_year" | "calendar_year" | "other" | "unknown";
  sort_key: number;
  fact_count: number;
  has_contradiction: boolean;
  has_corroboration: boolean;
  has_reconciled: boolean;
  facts: TimelineFact[];
}

export interface TimelineResponse {
  total_periods: number;
  total_facts: number;
  entries: TimelineEntry[];
}

export async function fetchTimeline(params?: {
  entity?: string;
  attribute?: string;
}): Promise<TimelineResponse> {
  const { data } = await apiClient.get("/api/timeline", { params });
  return data;
}
