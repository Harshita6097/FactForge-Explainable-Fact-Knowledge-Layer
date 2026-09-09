"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { FactDetailPanel } from "@/components/fact-detail-panel";
import { useScope } from "@/contexts/ScopeContext";
import { useChat } from "@/hooks/useChat";
import { ChatMessage, ChatCitation } from "@/lib/api/chat";

// ---------------------------------------------------------------------------
// Conflict card
// ---------------------------------------------------------------------------
function ConflictCard({ conflict }: { conflict: any }) {
  return (
    <div className="border border-amber-200 dark:border-amber-800 rounded-md p-3 bg-amber-50/50 dark:bg-amber-950/30 space-y-1">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
        <span>⚠</span>
        <span className="capitalize">{conflict.relationship_type}</span>
      </div>
      <div className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{conflict.src_entity} {conflict.src_attr}:</span>{" "}
        <span className="font-mono">{conflict.src_value}</span>
        {conflict.src_period && <span className="font-mono"> ({conflict.src_period})</span>}
        <span className="text-muted-foreground"> in {conflict.src_doc}</span>
        <span className="mx-1">vs</span>
        <span className="font-mono">{conflict.tgt_value}</span>
        {conflict.tgt_period && <span className="font-mono"> ({conflict.tgt_period})</span>}
        <span className="text-muted-foreground"> in {conflict.tgt_doc}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Citation card
// ---------------------------------------------------------------------------
function CitationCard({ citation, onOpen }: { citation: ChatCitation; onOpen: (id: string) => void }) {
  return (
    <button
      onClick={() => citation.fact_id && onOpen(citation.fact_id)}
      className="w-full text-left border rounded-md p-3 bg-muted/40 space-y-1 hover:border-primary/40 transition-colors"
    >
      <div className="flex items-center gap-2 text-xs">
        <span className="font-semibold text-foreground">{citation.entity}</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-muted-foreground">{citation.attribute}</span>
        <span className="ml-auto text-muted-foreground">
          {citation.document_name}
          {citation.page_number ? <span className="font-mono"> · p.{citation.page_number}</span> : ""}
        </span>
      </div>
      <p className="text-sm font-mono font-medium">{citation.value}</p>
      {citation.snippet && (
        <p className="text-xs italic text-muted-foreground line-clamp-2">"{citation.snippet}"</p>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------
function MessageBubble({
  message,
  onOpenFact,
}: {
  message: ChatMessage & { conflicts?: any[] };
  onOpenFact: (id: string) => void;
}) {
  const isUser = message.role === "user";
  const [showCitations, setShowCitations] = useState(false);
  const answerParts = message.content.split(/CITATIONS:/i);
  const mainAnswer = answerParts[0].trim();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div className={`max-w-[85%] space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap
            ${isUser
              ? "bg-primary text-primary-foreground rounded-br-sm"
              : "bg-muted text-foreground rounded-bl-sm"
            }`}
        >
          {mainAnswer}
        </div>

        {!isUser && message.citations.length > 0 && (
          <div className="w-full space-y-2">
            <button
              onClick={() => setShowCitations((v) => !v)}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1.5 transition-colors"
            >
              <span>📎</span>
              <span>{message.citations.length} citation{message.citations.length !== 1 ? "s" : ""}</span>
              <span className="text-xs">{showCitations ? "▲" : "▼"}</span>
              {message.facts_used > 0 && (
                <Badge variant="outline" className="ml-1 text-xs font-mono">
                  {message.facts_used} facts searched
                </Badge>
              )}
            </button>

            <AnimatePresence>
              {showCitations && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-2 overflow-hidden"
                >
                  {message.citations.map((c, i) => (
                    <CitationCard key={i} citation={c} onOpen={onOpenFact} />
                  ))}
                  {(message as any).conflicts?.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-xs font-semibold text-amber-600 uppercase tracking-wide">Known Conflicts</p>
                      {(message as any).conflicts.map((c: any, i: number) => (
                        <ConflictCard key={i} conflict={c} />
                      ))}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {!isUser && message.citations.length === 0 && message.facts_used === 0 && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <span>⚠️</span> No matching facts found in uploaded documents
          </p>
        )}
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Suggested questions
// ---------------------------------------------------------------------------
const SUGGESTIONS = [
  "What is the revenue for the latest fiscal year?",
  "Who is the CEO?",
  "What is the GDP growth rate?",
  "Are there any contradictions in the data?",
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ChatPage() {
  const { scope, scopeLabel } = useScope();
  const { messages, isLoading, error, sendMessage, clearChat } = useChat(scope.projectId ?? undefined);
  const [input, setInput] = useState("");
  const [openFactId, setOpenFactId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = () => {
    if (!input.trim()) return;
    // Pass scope document_id as context (backend can use it when supported)
    sendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-6 w-full flex flex-col gap-4 h-[calc(100vh-3.5rem)]">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Chat</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Every answer is grounded in your uploaded documents
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Scope indicator */}
          <span className="flex items-center gap-1.5 text-xs border rounded-full px-2.5 py-1 text-muted-foreground">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
            {scopeLabel}
          </span>
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearChat}>New chat</Button>
          )}
        </div>
      </div>

      <Separator />

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto min-h-0">
        {messages.length === 0 && (
          <div className="space-y-4 pt-4">
            <p className="text-sm text-muted-foreground text-center">
              Ask anything about your uploaded documents
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="text-left text-sm border rounded-lg p-3 hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg as any} onOpenFact={setOpenFactId} />
          ))}
        </AnimatePresence>

        {isLoading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
            <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1 items-center h-4">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground inline-block"
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {error && <p className="text-xs text-destructive text-center">{error}</p>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 pt-2 border-t">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents…"
          disabled={isLoading}
          className="flex-1"
        />
        <Button onClick={handleSend} disabled={isLoading || !input.trim()}>
          {isLoading ? "…" : "Send"}
        </Button>
      </div>

      {/* Fact detail slide-over */}
      <FactDetailPanel factId={openFactId} onClose={() => setOpenFactId(null)} />
    </div>
  );
}
