import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  askQuestion, fetchSessions, fetchSessionMessages,
  deleteSession, ChatMessage, AskResponse,
} from "@/lib/api/chat";

export function useChatSessions() {
  return useQuery({ queryKey: ["chat", "sessions"], queryFn: fetchSessions });
}

export function useSessionMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ["chat", "messages", sessionId],
    queryFn: () => fetchSessionMessages(sessionId!),
    enabled: !!sessionId,
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSession,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat", "sessions"] }),
  });
}

export function useChat() {
  const qc = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    if (!question.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: question,
      citations: [],
      facts_used: 0,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    try {
      const result: AskResponse = await askQuestion(question, sessionId ?? undefined);

      if (!sessionId) {
        setSessionId(result.session_id);
        qc.invalidateQueries({ queryKey: ["chat", "sessions"] });
      }

      const assistantMsg: ChatMessage = {
        id: result.message_id,
        role: "assistant",
        content: result.answer,
        citations: result.citations,
        facts_used: result.facts_used,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setError(e.message || "Failed to get answer");
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, isLoading, qc]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setError(null);
  }, []);

  return { messages, isLoading, error, sessionId, sendMessage, clearChat };
}
