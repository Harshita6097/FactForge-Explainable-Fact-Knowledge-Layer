"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useCanonicalFact } from "@/hooks/useKnowledge";
import { ReasoningStep, Relationship } from "@/types";

// ---------------------------------------------------------------------------
// Confidence bar
// ---------------------------------------------------------------------------
function ConfidenceBar({ value, positive }: { value: number; positive: boolean }) {
  const pct = Math.min(Math.abs(value) * 100, 100);
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${positive ? "bg-green-500" : "bg-red-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono tabular-nums ${positive ? "text-green-600" : "text-red-500"}`}>
        {positive ? "+" : ""}{(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reasoning chain
// ---------------------------------------------------------------------------
const STEP_COLORS: Record<string, string> = {
  match: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  different: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  conflict: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  corroborated: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  contradiction: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  reconciled: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  related: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
};

function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
  return (
    <div className="space-y-2">
      {steps.map((s) => (
        <div key={s.step} className="flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
            {s.step}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-foreground">{s.check}</span>
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

// ---------------------------------------------------------------------------
// Relationship card with reasoning
// ---------------------------------------------------------------------------
const REL_STYLES: Record<string, { badge: string; border: string; label: string }> = {
  corroborated: { badge: "bg-green-100 text-green-800", border: "border-l-green-500", label: "✓ Corroborated" },
  contradiction: { badge: "bg-red-100 text-red-800", border: "border-l-red-500", label: "✗ Contradiction" },
  reconciled: { badge: "bg-amber-100 text-amber-800", border: "border-l-amber-500", label: "⟳ Reconciled" },
  related: { badge: "bg-blue-100 text-blue-800", border: "border-l-blue-500", label: "~ Related" },
};

function RelationshipInspector({ rel, sourceFactIds }: { rel: Relationship; sourceFactIds: string[] }) {
  const [open, setOpen] = useState(false);
  const style = REL_STYLES[rel.relationship_type] ?? REL_STYLES.related;
  const isSource = sourceFactIds.includes(rel.source_fact_id);
  const other = isSource ? rel.target_fact : rel.source_fact;

  return (
    <Card className={`border-l-4 ${style.border}`}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
            {style.label}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{Math.round(rel.confidence * 100)}% confidence</span>
            {rel.reasoning_steps && rel.reasoning_steps.length > 0 && (
              <button
                onClick={() => setOpen((v) => !v)}
                className="text-xs text-primary hover:underline"
              >
                {open ? "Hide reasoning" : "Show reasoning"}
              </button>
            )}
          </div>
        </div>

        {other && (
          <div className="text-sm space-y-0.5">
            <span className="font-medium">{other.entity}</span>
            <span className="text-muted-foreground"> · {other.attribute}</span>
            <span className="ml-2 font-medium">{(other as any).canonical_value || (other as any).raw_value}</span>
            {(other as any).period && (
              <Badge variant="outline" className="ml-2 text-xs">{(other as any).period}</Badge>
            )}
            {(other as any).original_filename && (
              <p className="text-xs text-muted-foreground mt-1">
                {(other as any).original_filename} · p.{(other as any).page_number}
              </p>
            )}
          </div>
        )}

        {rel.explanation && (
          <p className="text-xs text-muted-foreground italic border-l-2 border-muted pl-2">
            {rel.explanation}
          </p>
        )}

        <AnimatePresence>
          {open && rel.reasoning_steps && rel.reasoning_steps.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <Separator className="my-2" />
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                Reasoning Chain
              </p>
              <ReasoningChain steps={rel.reasoning_steps} />
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function CanonicalFactDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: cf, isLoading } = useCanonicalFact(id);

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full">
          <div className="space-y-4 animate-pulse">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}><CardContent className="p-5 h-20" /></Card>
            ))}
          </div>
        </main>
      </div>
    );
  }

  if (!cf) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full">
          <p className="text-muted-foreground">Fact not found.</p>
        </main>
      </div>
    );
  }

  const hasConflict = cf.conflicting_count > 0;

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full space-y-6">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>← Back</Button>

        {/* Canonical fact summary */}
        <Card className={hasConflict ? "border-red-200 dark:border-red-900" : ""}>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs text-primary font-semibold uppercase tracking-wide mb-1">
                  {cf.canonical_entity}
                </p>
                <CardTitle className="text-2xl">{cf.canonical_attribute}</CardTitle>
              </div>
              <div className="text-right">
                <div className={`text-2xl font-bold ${
                  cf.confidence >= 0.8 ? "text-green-600" :
                  cf.confidence >= 0.6 ? "text-amber-600" : "text-red-500"
                }`}>
                  {Math.round(cf.confidence * 100)}%
                </div>
                <div className="text-xs text-muted-foreground">confidence</div>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground text-xs mb-1">Canonical Value</p>
                <p className="text-xl font-bold">
                  {cf.canonical_value || "—"}
                  {cf.canonical_unit && (
                    <span className="text-sm font-normal text-muted-foreground ml-1">{cf.canonical_unit}</span>
                  )}
                </p>
              </div>
              {cf.period && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Period</p>
                  <Badge variant="outline">{cf.period}</Badge>
                </div>
              )}
            </div>

            <div className="flex gap-2 flex-wrap">
              <span className="text-xs bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-400 px-2 py-1 rounded-full font-medium">
                ✓ {cf.supporting_count} supporting document{cf.supporting_count !== 1 ? "s" : ""}
              </span>
              {hasConflict && (
                <span className="text-xs bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400 px-2 py-1 rounded-full font-medium">
                  ✗ {cf.conflicting_count} conflict{cf.conflicting_count !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Confidence breakdown */}
        {cf.raw_facts && cf.raw_facts[0]?.confidence_breakdown && (
          <div className="space-y-3">
            <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
              Confidence Breakdown
            </h2>
            <Card>
              <CardContent className="p-4 space-y-3">
                {cf.raw_facts[0].confidence_breakdown.map((signal, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className={`text-xs w-4 ${signal.positive ? "text-green-500" : "text-red-400"}`}>
                      {signal.positive ? "+" : "−"}
                    </span>
                    <span className="text-xs text-muted-foreground flex-1 min-w-0 truncate">
                      {signal.signal}
                    </span>
                    <span className="text-xs text-muted-foreground shrink-0">{signal.weight}</span>
                    <ConfidenceBar value={signal.value} positive={signal.positive} />
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Evidence across all supporting documents */}
        <div className="space-y-3">
          <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
            Evidence ({cf.raw_facts?.length ?? 0} source{(cf.raw_facts?.length ?? 0) !== 1 ? "s" : ""})
          </h2>
          {cf.raw_facts?.map((rf, i) => (
            <Card key={rf.id} className="border-l-4 border-l-primary">
              <CardContent className="p-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-semibold text-foreground">
                      {rf.evidence?.[0]?.document_name ?? "Unknown document"}
                    </span>
                    {rf.evidence?.[0]?.page_number && (
                      <>
                        <span>·</span>
                        <span>Page {rf.evidence[0].page_number}</span>
                      </>
                    )}
                  </div>
                  <Badge variant="outline" className="text-xs">
                    Raw: {rf.raw_value}
                  </Badge>
                </div>
                <Separator />
                {rf.evidence?.[0]?.snippet && (
                  <blockquote className="text-sm italic text-muted-foreground border-l-2 border-muted pl-3">
                    "{rf.evidence[0].snippet}"
                  </blockquote>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Relationships with reasoning */}
        {cf.relationships && cf.relationships.length > 0 && (
          <div className="space-y-3">
            <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
              Relationships ({cf.relationships.length})
            </h2>
            {cf.relationships.map((rel: any) => (
              <RelationshipInspector
                key={rel.id}
                rel={rel}
                sourceFactIds={cf.source_fact_ids}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
