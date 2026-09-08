"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { useRelationships, useRelationshipsSummary } from "@/hooks/useRelationships";
import { Relationship, ReasoningStep } from "@/types";

const REL_TYPES = ["all", "corroborated", "contradiction", "reconciled", "related"] as const;

const TYPE_STYLES: Record<string, { badge: string; border: string; label: string }> = {
  corroborated: { badge: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", border: "border-l-green-500", label: "✓ Corroborated" },
  contradiction: { badge: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200", border: "border-l-red-500", label: "✗ Contradiction" },
  reconciled:    { badge: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200", border: "border-l-amber-500", label: "⟳ Reconciled" },
  related:       { badge: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200", border: "border-l-blue-500", label: "~ Related" },
};

const STEP_COLORS: Record<string, string> = {
  match: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  different: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  conflict: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  corroborated: "bg-green-100 text-green-800",
  contradiction: "bg-red-100 text-red-800",
  reconciled: "bg-amber-100 text-amber-800",
  related: "bg-blue-100 text-blue-800",
};

function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
  return (
    <div className="space-y-2 pt-1">
      {steps.map((s) => (
        <div key={s.step} className="flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
            {s.step}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold">{s.check}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STEP_COLORS[s.result] ?? STEP_COLORS.info}`}>
                {s.result}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">{s.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function FactSide({ fact, label }: { fact: any; label: string }) {
  if (!fact) return null;
  return (
    <div className="flex-1 min-w-0 space-y-1">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="font-semibold text-sm">{fact.entity}</p>
      <p className="text-xs text-muted-foreground">{fact.attribute}</p>
      <p className="font-medium">{fact.canonical_value || fact.raw_value}
        {fact.unit && <span className="text-muted-foreground text-xs ml-1">{fact.unit}</span>}
      </p>
      {fact.period && <Badge variant="outline" className="text-xs">{fact.period}</Badge>}
      {fact.original_filename && (
        <p className="text-xs text-muted-foreground truncate">
          {fact.original_filename} · p.{fact.page_number}
        </p>
      )}
      {fact.snippet && (
        <p className="text-xs italic text-muted-foreground line-clamp-2">"{fact.snippet}"</p>
      )}
    </div>
  );
}

function RelationshipCard({ rel }: { rel: Relationship }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const style = TYPE_STYLES[rel.relationship_type] ?? TYPE_STYLES.related;
  const hasReasoning = rel.reasoning_steps && rel.reasoning_steps.length > 0;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className={`border-l-4 ${style.border}`}>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
              {style.label}
            </span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">
                {Math.round(rel.confidence * 100)}% confidence
              </span>
              {hasReasoning && (
                <button
                  onClick={() => setShowReasoning((v) => !v)}
                  className="text-xs text-primary hover:underline"
                >
                  {showReasoning ? "Hide reasoning" : "Show reasoning"}
                </button>
              )}
            </div>
          </div>

          <div className="flex gap-4 items-start">
            <FactSide fact={(rel as any).source_fact} label="Document A" />
            <div className="flex flex-col items-center justify-center pt-6 shrink-0">
              <div className="w-px h-8 bg-border" />
              <span className="text-xs text-muted-foreground my-1">vs</span>
              <div className="w-px h-8 bg-border" />
            </div>
            <FactSide fact={(rel as any).target_fact} label="Document B" />
          </div>

          {rel.explanation && (
            <>
              <Separator />
              <p className="text-xs text-muted-foreground italic">💡 {rel.explanation}</p>
            </>
          )}

          <AnimatePresence>
            {showReasoning && hasReasoning && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <Separator className="my-1" />
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Reasoning Chain</p>
                <ReasoningChain steps={rel.reasoning_steps!} />
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function RelationshipsPage() {
  const [activeType, setActiveType] = useState<string>("all");
  const { data: summary = {} } = useRelationshipsSummary();
  const { data: relationships = [], isLoading } = useRelationships(
    activeType !== "all" ? { relationship_type: activeType } : undefined
  );

  const total = Object.values(summary).reduce((a, b) => a + b, 0);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-5xl mx-auto px-4 py-10 w-full space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Relationship Explorer</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {total} cross-document relationships detected
          </p>
        </div>

        <Tabs value={activeType} onValueChange={setActiveType}>
          <TabsList>
            {REL_TYPES.map((t) => (
              <TabsTrigger key={t} value={t} className="capitalize">
                {t}
                {t !== "all" && summary[t] !== undefined && (
                  <span className="ml-1.5 text-xs opacity-70">({summary[t]})</span>
                )}
                {t === "all" && (
                  <span className="ml-1.5 text-xs opacity-70">({total})</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {isLoading && (
          <p className="text-muted-foreground text-sm">Loading relationships…</p>
        )}

        {!isLoading && relationships.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-4xl mb-3">🔗</p>
            <p className="font-medium">No relationships yet</p>
            <p className="text-sm mt-1">Upload multiple PDFs to detect cross-document relationships</p>
          </div>
        )}

        <AnimatePresence>
          <div className="space-y-4">
            {relationships.map((rel) => (
              <RelationshipCard key={rel.id} rel={rel} />
            ))}
          </div>
        </AnimatePresence>
      </main>
    </div>
  );
}
