"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
        <span>{conflict.src_value}</span>
        {conflict.src_period && <span> ({conflict.src_period})</span>}
        <span className="text-muted-foreground"> in {conflict.src_doc}</span>
        <span className="mx-1">vs</span>
        <span>{conflict.tgt_value}</span>
        {conflict.tgt_period && <span> ({conflict.tgt_period})</span>}
        <span className="text-muted-foreground"> in {conflict.tgt_doc}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Citation card
// ---------------------------------------------------------------------------
function CitationCard({ citation }: { citation: ChatCitation }) {
  return (
    <div className="border rounded-md p-3 bg-muted/40 space-y-1">
      <div className="flex items-center gap-2 text-xs">
        <span className="font-semibold text-foreground">{citation.entity}</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-muted-foreground">{citation.attribute}</span>
        <span className="ml-auto text-muted-foreground">
          {citation.document_name}
          {citation.page_number ? ` · p.${citation.page_number}` : ""}
        </span>
      </div>
      <p className="text-sm font-medium">{citation.value}</p>
      {citation.snippet && (
        <p className="text-xs italic text-muted-foreground line-clamp-2">
          "{citation.snippet}"
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [showCitations, setShowCitations] = useState(false);

  // Split answer from citations section for cleaner display
  const answerParts = message.content.split(/CITATIONS:/i);
  const mainAnswer = answerParts[0].trim();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div className={`max-w-[85%] space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap
            ${isUser
              ? "bg-primary text-primary-foreground rounded-br-sm"
              : "bg-muted text-foreground rounded-bl-sm"
            }`}
        >
          {mainAnswer}
        </div>

        {/* Citations toggle */}
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
                <Badge variant="outline" className="ml-1 text-xs">
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
                    <CitationCard key={i} citation={c} />
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

        {/* No answer indicator */}
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
  const { messages, isLoading, error, sendMessage, clearChat } = useChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = () => {
    if (!input.trim()) return;
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
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-4 py-6 w-full flex flex-col gap-4">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Chat</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              Ask questions — every answer is grounded in your uploaded documents
            </p>
          </div>
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearChat}>
              New chat
            </Button>
          )}
        </div>

        <Separator />

        {/* Messages */}
        <div className="flex-1 space-y-4 min-h-[400px]">
          {messages.length === 0 && (
            <div className="space-y-4 pt-4">
              <p className="text-sm text-muted-foreground text-center">
                Ask anything about your uploaded documents
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => { sendMessage(s); }}
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
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
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

          {error && (
            <p className="text-xs text-destructive text-center">{error}</p>
          )}

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
      </main>
    </div>
  );
}
