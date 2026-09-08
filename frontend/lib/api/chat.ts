import apiClient from "./client";

export interface ChatCitation {
  fact_id: string;
  document_name: string;
  page_number: number | null;
  snippet: string;
  entity: string;
  attribute: string;
  value: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  facts_used: number;
  created_at: string;
}

export interface ChatSession {
  id: string;
  created_at: string;
  title: string | null;
  message_count: number;
}

export interface AskResponse {
  session_id: string;
  message_id: string;
  answer: string;
  citations: ChatCitation[];
  facts_used: number;
  has_answer: boolean;
}

export async function askQuestion(
  question: string,
  session_id?: string
): Promise<AskResponse> {
  const { data } = await apiClient.post("/api/chat", { question, session_id });
  return data;
}

export async function fetchSessions(): Promise<ChatSession[]> {
  const { data } = await apiClient.get("/api/chat/sessions");
  return data;
}

export async function fetchSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const { data } = await apiClient.get(`/api/chat/sessions/${sessionId}/messages`);
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/api/chat/sessions/${sessionId}`);
}
