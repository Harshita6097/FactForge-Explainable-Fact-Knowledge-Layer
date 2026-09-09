"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useFact } from "@/hooks/useFacts";
import { useFactRelationships } from "@/hooks/useRelationships";
import { Relationship, ReasoningStep } from "@/types";

export const REL_STYLES: Record<string, { badge: string; label: string; icon: string }> = {
  corroborated:       { badge: "bg-green-100 text-green-800 border-green-200",  label: "Corroborated",       icon: "✓" },
  contradiction:      { badge: "bg-red-100 text-red-800 border-red-200",        label: "Contradiction",      icon: "✗" },
  reconciled:         { badge: "bg-amber-100 text-amber-800 border-amber-200",  label: "Reconciled",         icon: "⟳" },
  related:            { badge: "bg-blue-100 text-blue-800 border-blue-200",     label: "Related",            icon: "~" },
  extraction_failure: { badge: "bg-gray-100 text-gray-600 border-gray-200",    label: "Flagged",            icon: "⚠" },
};

function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
  return (
    <ol className="space-y-1.5 mt-2">
      {steps.map((s) => (
        <li key={s.step} className="flex gap-2 text-xs">
          <span className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5 ${
            s.result === "match"    ? "bg-green-100 text-green-700" :
            s.result === "conflict" ? "bg-red-100 text-red-700" :
            s.result === "flagged"  ? "bg-amber-100 text-amber-700" :
            "bg-muted text-muted-foreground"
          }`}>
            {s.step}
          </span>
          <div>
            <span className="font-semibold text-foreground">{s.check}: </span>
            <span className="text-muted-foreground">{s.detail}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}

function CrossDocEvidence({ rel, factId }: { rel: Relationship; factId: string }) {
  const [open, setOpen] = useState(false);
  const other = rel.source_fact_id === factId ? rel.target_fact : rel.source_fact;
  const style = REL_STYLES[rel.relationship_type] ?? REL_STYLES.related;

  return (
    <div className="border rounded-md overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded border ${style.badge}`}>
            {style.icon} {style.label}
          </span>
          {other && (
            <span className="text-xs text-muted-foreground truncate">
              <span className="font-medium text-foreground">{other.entity}</span>
              {" · "}{other.attribute}
              {other.period && <span className="font-mono"> ({other.period})</span>}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-mono text-muted-foreground">
            {Math.round(rel.confidence * 100)}%
          </span>
          <span className="text-muted-foreground text-xs">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* Expanded body */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-1 space-y-3 border-t bg-muted/10">
              {/* Other fact value */}
              {other && (
                <div className="text-xs space-y-1">
                  <p className="text-muted-foreground">Value from other document:</p>
                  <p className="font-mono font-semibold text-sm">
                    {other.canonical_value || other.raw_value}
                    {(other.canonical_unit || other.unit) && (
                      <span className="font-normal text-muted-foreground ml-1">
                        {other.canonical_unit || other.unit}
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* Source document */}
              {(rel.tgt_doc || rel.src_doc) && (
                <div className="text-xs text-muted-foreground">
                  📄 {rel.source_fact_id === factId ? rel.tgt_doc : rel.src_doc}
                  {other?.evidence && (
                    <span className="font-mono ml-1">
                      · p.{(other.evidence as any)?.page_number ?? "?"}
                    </span>
                  )}
                </div>
              )}

              {/* Reasoning summary */}
              {rel.reasoning_summary && (
                <div className="text-xs bg-muted/40 rounded px-2 py-1.5 text-muted-foreground italic">
                  💡 {rel.reasoning_summary}
                </div>
              )}

              {/* Step-by-step reasoning chain */}
              {rel.reasoning_steps && rel.reasoning_steps.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                    Reasoning chain
                  </p>
                  <ReasoningChain steps={rel.reasoning_steps} />
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface Props {
  factId: string | null;
  onClose: () => void;
}

export function FactDetailPanel({ factId, onClose }: Props) {
  const { data: fact, isLoading } = useFact(factId ?? "");
  const { data: relationships = [] } = useFactRelationships(factId ?? "");

  // Separate cross-doc relationships from same-doc
  const crossDocRels = relationships.filter(
    (r) => r.source_fact?.document_id !== r.target_fact?.document_id
  );

  // Relationship badge summary for the header
  const relCounts = relationships.reduce<Record<string, number>>((acc, r) => {
    acc[r.relationship_type] = (acc[r.relationship_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <AnimatePresence>
      {factId && (
        <>
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/30"
            onClick={onClose}
          />

          <motion.div
            key="panel"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-[460px] bg-background border-l shadow-xl flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b shrink-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-semibold text-sm">Fact Detail</p>
                {Object.entries(relCounts).map(([type, count]) => {
                  const s = REL_STYLES[type] ?? REL_STYLES.related;
                  return (
                    <span key={type} className={`text-[11px] font-semibold px-1.5 py-0.5 rounded border ${s.badge}`}>
                      {s.icon} {count} {s.label}
                    </span>
                  );
                })}
              </div>
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground transition-colors text-lg leading-none ml-2"
              >
                ✕
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">
              {isLoading && (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-10 rounded-md bg-muted/40 animate-pulse" />
                  ))}
                </div>
              )}

              {!isLoading && fact && (
                <>
                  {/* Identity */}
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-0.5">
                        {fact.entity}
                      </p>
                      <p className="text-lg font-bold">{fact.attribute}</p>
                    </div>
                    <Badge
                      variant={fact.confidence >= 0.8 ? "default" : fact.confidence >= 0.6 ? "secondary" : "destructive"}
                      className="shrink-0 font-mono"
                    >
                      {Math.round(fact.confidence * 100)}%
                    </Badge>
                  </div>

                  {/* Values grid */}
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground mb-0.5">Raw value</p>
                      <p className="font-mono font-medium">
                        {fact.raw_value}{fact.unit ? ` ${fact.unit}` : ""}
                      </p>
                    </div>
                    {fact.canonical_value && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-0.5">Canonical value</p>
                        <p className="font-mono font-medium">{fact.canonical_value}</p>
                      </div>
                    )}
                    {fact.period && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-0.5">Period</p>
                        <p className="font-mono font-medium">{fact.period}</p>
                      </div>
                    )}
                    {fact.canonical_unit && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-0.5">Unit</p>
                        <p className="font-medium">{fact.canonical_unit}</p>
                      </div>
                    )}
                  </div>

                  <Separator />

                  {/* Source evidence */}
                  <div className="space-y-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      Source Evidence ({fact.evidence?.length ?? 0})
                    </p>
                    {fact.evidence?.length === 0 && (
                      <p className="text-xs text-muted-foreground">No evidence linked.</p>
                    )}
                    {fact.evidence?.map((ev) => (
                      <div key={ev.id} className="border-l-2 border-primary pl-3 space-y-1">
                        <p className="text-xs text-muted-foreground">
                          <span className="font-medium text-foreground">{ev.document_name}</span>
                          {" · "}
                          <span className="font-mono">p.{ev.page_number}</span>
                        </p>
                        <blockquote className="text-xs italic text-muted-foreground leading-relaxed">
                          &ldquo;{ev.snippet}&rdquo;
                        </blockquote>
                      </div>
                    ))}
                  </div>

                  {/* Cross-document evidence */}
                  {crossDocRels.length > 0 && (
                    <>
                      <Separator />
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          Cross-Document Evidence ({crossDocRels.length})
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Facts from other PDFs that relate to this one, with the system&apos;s reasoning.
                        </p>
                        {crossDocRels.map((rel) => (
                          <CrossDocEvidence key={rel.id} rel={rel} factId={factId!} />
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
