"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useFact } from "@/hooks/useFacts";
import { useFactRelationships } from "@/hooks/useRelationships";
import { REL_STYLES } from "@/components/fact-detail-panel";
import { Evidence, Relationship, ReasoningStep } from "@/types";

function confidenceVariant(c: number): "default" | "secondary" | "destructive" {
  if (c >= 0.8) return "default";
  if (c >= 0.6) return "secondary";
  return "destructive";
}

// ---------------------------------------------------------------------------
// Snippet Viewer — highlights the search term inside the snippet text
// ---------------------------------------------------------------------------
function SnippetViewer({
  ev,
  searchTerm,
}: {
  ev: Evidence;
  searchTerm?: string;
}) {
  const [open, setOpen] = useState(false);

  const highlighted = searchTerm
    ? ev.snippet.replace(
        new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"),
        '<mark class="bg-yellow-200 text-yellow-900 rounded px-0.5">$1</mark>'
      )
    : ev.snippet;

  return (
    <Card className="border-l-4 border-l-primary">
      <CardContent className="p-4 space-y-2">
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{ev.document_name}</span>
            <span>·</span>
            <button
              onClick={() => setOpen((v) => !v)}
              className="font-mono text-primary hover:underline"
            >
              p.{ev.page_number} {open ? "▲" : "▼"}
            </button>
          </div>
          <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
            {open ? "Hide snippet" : "Show snippet"}
          </span>
        </div>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <Separator className="my-2" />
              <blockquote
                className="text-sm text-muted-foreground border-l-2 border-muted pl-3 leading-relaxed"
                dangerouslySetInnerHTML={{ __html: `&ldquo;${highlighted}&rdquo;` }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Reasoning chain display
// ---------------------------------------------------------------------------
function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
  return (
    <ol className="space-y-2 mt-2">
      {steps.map((s) => (
        <li key={s.step} className="flex gap-2.5 text-sm">
          <span
            className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold mt-0.5 ${
              s.result === "match"
                ? "bg-green-100 text-green-700"
                : s.result === "conflict"
                ? "bg-red-100 text-red-700"
                : s.result === "flagged"
                ? "bg-amber-100 text-amber-700"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {s.step}
          </span>
          <div>
            <span className="font-semibold">{s.check}: </span>
            <span className="text-muted-foreground">{s.detail}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Cross-document relationship card
// ---------------------------------------------------------------------------
function CrossDocCard({ rel, factId }: { rel: Relationship; factId: string }) {
  const [open, setOpen] = useState(false);
  const other = rel.source_fact_id === factId ? rel.target_fact : rel.source_fact;
  const style = REL_STYLES[rel.relationship_type] ?? REL_STYLES.related;
  const srcDoc = rel.source_fact_id === factId ? rel.tgt_doc : rel.src_doc;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between gap-3">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${style.badge}`}>
            {style.icon} {style.label}
          </span>
          <span className="text-xs text-muted-foreground font-mono">
            {Math.round(rel.confidence * 100)}% confidence
          </span>
        </div>

        {/* Other fact */}
        {other && (
          <div className="text-sm space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold">{other.entity}</span>
              <span className="text-muted-foreground">· {other.attribute}</span>
              {other.period && (
                <Badge variant="outline" className="text-xs">{other.period}</Badge>
              )}
            </div>
            <p className="font-mono text-base font-bold">
              {other.canonical_value || other.raw_value}
              {(other.canonical_unit || other.unit) && (
                <span className="font-normal text-sm text-muted-foreground ml-1">
                  {other.canonical_unit || other.unit}
                </span>
              )}
            </p>
            {srcDoc && (
              <p className="text-xs text-muted-foreground">
                📄 {srcDoc}
                {(other.evidence as any)?.page_number && (
                  <span className="font-mono ml-1">· p.{(other.evidence as any).page_number}</span>
                )}
              </p>
            )}
          </div>
        )}

        {/* Reasoning summary */}
        {rel.reasoning_summary && (
          <div className="text-xs bg-muted/40 rounded px-3 py-2 text-muted-foreground italic">
            💡 {rel.reasoning_summary}
          </div>
        )}

        {/* Expandable reasoning chain */}
        {rel.reasoning_steps && rel.reasoning_steps.length > 0 && (
          <>
            <button
              onClick={() => setOpen((v) => !v)}
              className="text-xs text-primary hover:underline"
            >
              {open ? "Hide" : "Show"} reasoning chain ({rel.reasoning_steps.length} steps)
            </button>
            <AnimatePresence>
              {open && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="overflow-hidden"
                >
                  <ReasoningChain steps={rel.reasoning_steps} />
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function FactDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: fact, isLoading } = useFact(id);
  const { data: relationships = [] } = useFactRelationships(id);

  const crossDocRels = relationships.filter(
    (r) => r.source_fact?.document_id !== r.target_fact?.document_id
  );

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full">
          <p className="text-muted-foreground">Loading…</p>
        </main>
      </div>
    );
  }

  if (!fact) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full">
          <p className="text-muted-foreground">Fact not found.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full space-y-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>← Back</Button>
        </div>

        {/* Fact summary */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                  {fact.entity}
                </p>
                <CardTitle className="text-xl">{fact.attribute}</CardTitle>
              </div>
              <Badge variant={confidenceVariant(fact.confidence)}>
                {Math.round(fact.confidence * 100)}% confidence
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground text-xs mb-1">Raw Value</p>
                <p className="font-medium">{fact.raw_value}{fact.unit ? ` ${fact.unit}` : ""}</p>
              </div>
              {fact.canonical_value && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Canonical Value</p>
                  <p className="font-medium">{fact.canonical_value}</p>
                </div>
              )}
              {fact.period && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Period</p>
                  <p className="font-medium">{fact.period}</p>
                </div>
              )}
              {fact.canonical_unit && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Unit</p>
                  <p className="font-medium">{fact.canonical_unit}</p>
                </div>
              )}
            </div>

            {/* Relationship badge summary */}
            {relationships.length > 0 && (
              <div className="flex gap-1.5 flex-wrap pt-2 border-t">
                {Object.entries(
                  relationships.reduce<Record<string, number>>((acc, r) => {
                    acc[r.relationship_type] = (acc[r.relationship_type] ?? 0) + 1;
                    return acc;
                  }, {})
                ).map(([type, count]) => {
                  const s = REL_STYLES[type] ?? REL_STYLES.related;
                  return (
                    <span key={type} className={`text-xs font-semibold px-2 py-0.5 rounded border ${s.badge}`}>
                      {s.icon} {count} {s.label}
                    </span>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Source evidence with snippet viewer */}
        <div className="space-y-3">
          <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
            Source Evidence ({fact.evidence?.length ?? 0})
          </h2>
          {fact.evidence?.length === 0 && (
            <p className="text-sm text-muted-foreground">No evidence linked.</p>
          )}
          {fact.evidence?.map((ev) => (
            <SnippetViewer key={ev.id} ev={ev} searchTerm={fact.raw_value} />
          ))}
        </div>

        {/* Cross-document evidence */}
        {crossDocRels.length > 0 && (
          <div className="space-y-3">
            <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
              Cross-Document Evidence ({crossDocRels.length})
            </h2>
            <p className="text-xs text-muted-foreground">
              Facts from other PDFs that relate to this one, with the system&apos;s step-by-step reasoning.
            </p>
            {crossDocRels.map((rel) => (
              <CrossDocCard key={rel.id} rel={rel} factId={id} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
