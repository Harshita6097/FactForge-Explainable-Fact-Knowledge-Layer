export type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  page_count: number;
  status: DocumentStatus;
  uploaded_at: string;
  processed_at: string | null;
}

export interface Evidence {
  id: string;
  fact_id: string;
  document_id: string;
  page_number: number;
  snippet: string;
  document_name?: string;
}

export interface Fact {
  id: string;
  document_id: string;
  entity: string;
  attribute: string;
  canonical_value: string | null;
  raw_value: string;
  unit: string | null;
  period: string | null;
  confidence: number;
  created_at: string;
  evidence?: Evidence[];
}

export type RelationshipType = "corroborated" | "contradiction" | "reconciled" | "related";

export interface Relationship {
  id: string;
  source_fact_id: string;
  target_fact_id: string;
  relationship_type: RelationshipType;
  explanation: string | null;
  confidence: number;
  created_at: string;
  source_fact?: Fact;
  target_fact?: Fact;
}

export interface DashboardStats {
  documents: number;
  facts: number;
  corroborated: number;
  contradictions: number;
  reconciled: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Evidence[];
}

export interface ApiError {
  detail: string;
}
