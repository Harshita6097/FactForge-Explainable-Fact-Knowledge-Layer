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

export interface ConfidenceSignal {
  signal: string;
  value: number;
  weight: string;
  positive: boolean;
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
  confidence_breakdown?: ConfidenceSignal[];
}

export interface CanonicalFact {
  id: string;
  entity: string;
  canonical_entity: string;
  attribute: string;
  canonical_attribute: string;
  canonical_value: string | null;
  canonical_unit: string | null;
  period: string | null;
  confidence: number;
  supporting_count: number;
  conflicting_count: number;
  corroboration_count: number;
  source_fact_ids: string[];
  raw_facts?: Fact[];
  relationships?: Relationship[];
  created_at: string;
  updated_at: string;
}

export type RelationshipType = "corroborated" | "contradiction" | "reconciled" | "related";

export interface ReasoningStep {
  step: number;
  check: string;
  result: string;
  detail: string;
}

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
  reasoning_steps?: ReasoningStep[];
}

export interface DashboardStats {
  documents: number;
  facts: number;
  canonical_facts: number;
  multi_document_facts: number;
  corroborated: number;
  contradictions: number;
  reconciled: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Evidence[];
  conflicts?: ConflictInfo[];
}

export interface ConflictInfo {
  relationship_type: string;
  explanation: string;
  src_entity: string;
  src_attr: string;
  src_value: string;
  src_period: string;
  src_doc: string;
  tgt_value: string;
  tgt_period: string;
  tgt_doc: string;
}

export interface ApiError {
  detail: string;
}
