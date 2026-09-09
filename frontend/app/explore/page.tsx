"use client";

import { useState, Suspense, lazy } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FactDetailPanel } from "@/components/fact-detail-panel";
import { useScope } from "@/contexts/ScopeContext";
import { useFacts } from "@/hooks/useFacts";
import { useRelationships, useRelationshipsSummary, useExtractionFailures } from "@/hooks/useRelationships";
import { useTimeline } from "@/hooks/useTimeline";
import { useCases } from "@/hooks/useCases";
import { Fact, Relationship, ReasoningStep, ExtractionFailure } from "@/types";
import { TimelineEntry, TimelineFact } from "@/lib/api/timeline";

const GraphView = lazy(() =>
  import("@/components/graph-view").then((m) => ({ default: m.GraphView }))
);

type View = "table" | "graph" | "relationships" | "timeline" | "failures" | "cases";

const VIEWS: { id: View; label: string }[] = [
  { id: "table",         label: "Facts"         },
  { id: "graph",         label: "Graph"         },
  { id: "relationships", label: "Relationships" },
  { id: "timeline",      label: "Timeline"      },
  { id: "failures",      label: "⚠ Failures"    },
  { id: "cases",         label: "📋 Cases"       },
];

const REL_TYPES = ["all", "corroborated", "contradiction", "reconciled", "related"] as const;

const TYPE_STYLES: Record<string, { badge: string; border: string; label: string }> = {
  corroborated: { badge: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", border: "border-l-green-500", label: "✓ Corroborated" },
  contradiction: { badge: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",        border: "border-l-red-500",   label: "✗ Contradiction" },
  reconciled:    { badge: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200", border: "border-l-amber-500", label: "⟳ Reconciled"   },
  related:       { badge: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",     border: "border-l-blue-500",  label: "~ Related"       },
};

const STEP_COLORS: Record<string, string> = {
  match: "bg-green-100 text-green-800", different: "bg-amber-100 text-amber-800",
  conflict: "bg-red-100 text-red-800",  info: "bg-blue-100 text-blue-800",
  corroborated: "bg-green-100 text-green-800", contradiction: "bg-red-100 text-red-800",
  reconciled: "bg-amber-100 text-amber-800",   related: "bg-blue-100 text-blue-800",
};

// ---------------------------------------------------------------------------
// Shared empty state
// ---------------------------------------------------------------------------
function EmptyState({ icon, title, sub }: { icon: string; title: string; sub: string }) {
  return (
    <div className="text-center py-20 text-muted-foreground">
      <p className="text-4xl mb-3">{icon}</p>
      <p className="font-medium text-sm">{title}</p>
      <p className="text-xs mt-1">{sub}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Facts table view
// ---------------------------------------------------------------------------
function FactCard({ fact, onOpen }: { fact: Fact; onOpen: (id: string) => void }) {
  return (
    <div
      className="border rounded-lg p-4 hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer"
      onClick={() => onOpen(fact.id)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{fact.entity}</span>
            <span>·</span>
            <span>{fact.attribute}</span>
            {fact.period && <Badge variant="outline" className="text-xs font-mono">{fact.period}</Badge>}
          </div>
          <p className="text-lg font-bold font-mono">
            {fact.canonical_value || fact.raw_value}
            {(fact.canonical_unit || fact.unit) && (
              <span className="text-sm font-normal text-muted-foreground ml-1">
                {fact.canonical_unit || fact.unit}
              </span>
            )}
          </p>
        </div>
        <div className={`text-sm font-bold font-mono shrink-0 ${
          fact.confidence >= 0.8 ? "text-green-600" :
          fact.confidence >= 0.6 ? "text-amber-600" : "text-red-500"
        }`}>
          {Math.round(fact.confidence * 100)}%
        </div>
      </div>
    </div>
  );
}

function TableView({ search, projectId, documentId, onOpenFact }: {
  search: string; projectId?: string; documentId?: string; onOpenFact: (id: string) => void;
}) {
  const params = documentId ? { document_id: documentId }
    : projectId ? { project_id: projectId }
    : undefined;
  const { data: facts = [], isLoading } = useFacts(params);

  const filtered = facts.filter((f) => {
    const q = search.toLowerCase();
    return !q || f.entity.toLowerCase().includes(q) || f.attribute.toLowerCase().includes(q) ||
      f.raw_value.toLowerCase().includes(q) || (f.period?.toLowerCase().includes(q) ?? false);
  });

  const grouped = filtered.reduce<Record<string, Fact[]>>((acc, f) => {
    const key = f.attribute || "Other";
    (acc[key] ??= []).push(f);
    return acc;
  }, {});

  if (isLoading) return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="border rounded-lg p-4 h-20 animate-pulse bg-muted/30" />
      ))}
    </div>
  );

  if (facts.length === 0) return (
    <EmptyState icon="⬡" title="No facts yet"
      sub={projectId ? "Upload PDFs to this project to extract facts" : "Select a project or upload a PDF"} />
  );
  if (filtered.length === 0) return (
    <p className="text-muted-foreground text-sm text-center py-8">No facts match your search.</p>
  );

  return (
    <div className="space-y-6">
      {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([attribute, attrFacts]) => (
        <motion.div key={attribute} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{attribute}</p>
            <span className="text-xs text-muted-foreground">({attrFacts.length})</span>
          </div>
          <div className="space-y-2">
            {attrFacts.map((fact) => <FactCard key={fact.id} fact={fact} onOpen={onOpenFact} />)}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Graph view wrapper
// ---------------------------------------------------------------------------
function GraphViewWrapper({ projectId, documentId, onOpenFact }: {
  projectId?: string; documentId?: string; onOpenFact: (id: string) => void;
}) {
  const params = documentId ? { document_id: documentId }
    : projectId ? { project_id: projectId }
    : undefined;
  const { data: facts = [], isLoading: factsLoading } = useFacts(params);
  const relParams = projectId ? { project_id: projectId } : undefined;
  const { data: relationships = [], isLoading: relsLoading } = useRelationships(relParams);

  if (factsLoading || relsLoading) return (
    <div className="h-[600px] border rounded-xl flex items-center justify-center">
      <p className="text-muted-foreground text-sm">Building graph…</p>
    </div>
  );

  return (
    <Suspense fallback={
      <div className="h-[600px] border rounded-xl flex items-center justify-center">
        <p className="text-muted-foreground text-sm">Loading graph…</p>
      </div>
    }>
      <GraphView facts={facts} relationships={relationships} onOpenFact={onOpenFact} />
    </Suspense>
  );
}

// ---------------------------------------------------------------------------
// Relationships view
// ---------------------------------------------------------------------------
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

function FactSide({ fact, label, onOpen }: { fact: any; label: string; onOpen: (id: string) => void }) {
  if (!fact) return null;
  return (
    <div className="flex-1 min-w-0 space-y-1">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="font-semibold text-sm">{fact.entity}</p>
      <p className="text-xs text-muted-foreground">{fact.attribute}</p>
      <p className="font-mono font-medium">
        {fact.canonical_value || fact.raw_value}
        {fact.unit && <span className="text-muted-foreground text-xs ml-1">{fact.unit}</span>}
      </p>
      {fact.period && <Badge variant="outline" className="text-xs font-mono">{fact.period}</Badge>}
      {fact.original_filename && (
        <p className="text-xs text-muted-foreground truncate">
          {fact.original_filename} · <span className="font-mono">p.{fact.page_number}</span>
        </p>
      )}
      {fact.snippet && (
        <p className="text-xs italic text-muted-foreground line-clamp-2">"{fact.snippet}"</p>
      )}
      <button onClick={() => onOpen(fact.id)} className="text-xs text-primary hover:underline">Detail →</button>
    </div>
  );
}

function RelationshipCard({ rel, onOpenFact }: { rel: Relationship; onOpenFact: (id: string) => void }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const style = TYPE_STYLES[rel.relationship_type] ?? TYPE_STYLES.related;
  const hasReasoning = rel.reasoning_steps && rel.reasoning_steps.length > 0;

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className={`border-l-4 ${style.border}`}>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>{style.label}</span>
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-muted-foreground">{Math.round(rel.confidence * 100)}% confidence</span>
              {hasReasoning && (
                <button onClick={() => setShowReasoning((v) => !v)} className="text-xs text-primary hover:underline">
                  {showReasoning ? "Hide reasoning" : "Show reasoning"}
                </button>
              )}
            </div>
          </div>
          <div className="flex gap-4 items-start">
            <FactSide fact={(rel as any).source_fact} label="Document A" onOpen={onOpenFact} />
            <div className="flex flex-col items-center justify-center pt-6 shrink-0">
              <div className="w-px h-8 bg-border" />
              <span className="text-xs text-muted-foreground my-1">vs</span>
              <div className="w-px h-8 bg-border" />
            </div>
            <FactSide fact={(rel as any).target_fact} label="Document B" onOpen={onOpenFact} />
          </div>
          {rel.explanation && (
            <><Separator /><p className="text-xs text-muted-foreground italic">💡 {rel.explanation}</p></>
          )}
          <AnimatePresence>
            {showReasoning && hasReasoning && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
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

function RelationshipsView({ projectId, onOpenFact }: { projectId?: string; onOpenFact: (id: string) => void }) {
  const [activeType, setActiveType] = useState<string>("all");
  const summaryParams = projectId ? { project_id: projectId } : undefined;
  const { data: summary = {} } = useRelationshipsSummary(summaryParams);
  const relParams = {
    ...(activeType !== "all" ? { relationship_type: activeType } : {}),
    ...(projectId ? { project_id: projectId } : {}),
  };
  const { data: relationships = [], isLoading } = useRelationships(
    Object.keys(relParams).length ? relParams : undefined
  );
  const total = Object.values(summary as Record<string, number>).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      <Tabs value={activeType} onValueChange={setActiveType}>
        <TabsList>
          {REL_TYPES.map((t) => (
            <TabsTrigger key={t} value={t} className="capitalize">
              {t}<span className="ml-1.5 text-xs opacity-70">({t === "all" ? total : (summary as any)[t] ?? 0})</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {isLoading && <p className="text-muted-foreground text-sm">Loading relationships…</p>}
      {!isLoading && relationships.length === 0 && (
        <EmptyState icon="🔗" title="No relationships yet" sub="Upload multiple PDFs to detect cross-document relationships" />
      )}
      <div className="space-y-4">
        {relationships.map((rel) => <RelationshipCard key={rel.id} rel={rel} onOpenFact={onOpenFact} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Timeline view
// ---------------------------------------------------------------------------
function periodIcon(type: TimelineEntry["period_type"]) {
  switch (type) {
    case "quarter": return "📊"; case "fiscal_year": return "📅";
    case "calendar_year": return "🗓️"; default: return "📌";
  }
}

function TimelineFactRow({ fact, onOpen }: { fact: TimelineFact; onOpen: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-l-2 border-border pl-3 py-1 cursor-pointer hover:border-primary/50 transition-colors"
      onClick={() => setExpanded((v) => !v)}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="text-xs font-semibold text-muted-foreground">{fact.entity}</span>
          <span className="text-xs text-muted-foreground mx-1">·</span>
          <span className="text-xs text-muted-foreground">{fact.attribute}</span>
          <p className="text-sm font-mono font-medium mt-0.5">
            {fact.canonical_value || fact.raw_value}
            {fact.unit && <span className="text-muted-foreground text-xs ml-1">{fact.unit}</span>}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {fact.relationships.includes("contradiction") && <span className="w-2 h-2 rounded-full bg-red-500" />}
          {fact.relationships.includes("corroborated") && <span className="w-2 h-2 rounded-full bg-green-500" />}
          {fact.relationships.includes("reconciled") && <span className="w-2 h-2 rounded-full bg-amber-500" />}
          <Badge variant="outline" className="text-xs font-mono">{Math.round(fact.confidence * 100)}%</Badge>
          <button onClick={(e) => { e.stopPropagation(); onOpen(fact.id); }} className="text-xs text-primary hover:underline">→</button>
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }} className="mt-2 space-y-1 overflow-hidden">
            <p className="text-xs text-muted-foreground">
              📄 {fact.document}{fact.page_number ? <span className="font-mono"> · p.{fact.page_number}</span> : ""}
            </p>
            {fact.snippet && (
              <p className="text-xs italic text-muted-foreground border-l-2 border-muted pl-2">"{fact.snippet}"</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TimelineNode({ entry, index, onOpenFact }: { entry: TimelineEntry; index: number; onOpenFact: (id: string) => void }) {
  const [open, setOpen] = useState(index < 3);
  return (
    <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.04 }} className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-3 h-3 rounded-full border-2 mt-1 shrink-0 cursor-pointer transition-colors
          ${entry.has_contradiction ? "border-red-500 bg-red-100" : entry.has_corroboration ? "border-green-500 bg-green-100" : "border-primary bg-primary/10"}`}
          onClick={() => setOpen((v) => !v)} />
        <div className="w-px flex-1 bg-border mt-1" />
      </div>
      <div className="pb-8 flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2 cursor-pointer select-none" onClick={() => setOpen((v) => !v)}>
          <span className="text-base">{periodIcon(entry.period_type)}</span>
          <span className="font-semibold font-mono">{entry.period}</span>
          <Badge variant="secondary" className="text-xs">{entry.fact_count} facts</Badge>
          {entry.has_contradiction && <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">✗ Contradiction</span>}
          {entry.has_corroboration && <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">✓ Corroborated</span>}
          {entry.has_reconciled && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">⟳ Reconciled</span>}
          <span className="ml-auto text-xs text-muted-foreground">{open ? "▲" : "▼"}</span>
        </div>
        <AnimatePresence>
          {open && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
              <Card><CardContent className="p-4 space-y-3">
                {entry.facts.map((fact) => <TimelineFactRow key={fact.id} fact={fact} onOpen={onOpenFact} />)}
              </CardContent></Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function TimelineView({ projectId, documentId, onOpenFact }: { projectId?: string; documentId?: string; onOpenFact: (id: string) => void }) {
  const [entityFilter, setEntityFilter] = useState("");
  const [attrFilter, setAttrFilter] = useState("");
  const { data, isLoading } = useTimeline({
    entity: entityFilter || undefined,
    attribute: attrFilter || undefined,
    project_id: projectId,
    document_id: documentId,
  });
  const entries = data?.entries ?? [];

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <Input placeholder="Filter by entity…" value={entityFilter} onChange={(e) => setEntityFilter(e.target.value)} className="max-w-xs" />
        <Input placeholder="Filter by attribute…" value={attrFilter} onChange={(e) => setAttrFilter(e.target.value)} className="max-w-xs" />
      </div>
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> Corroborated</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> Contradiction</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Reconciled</span>
      </div>
      {isLoading && <p className="text-muted-foreground text-sm">Building timeline…</p>}
      {!isLoading && entries.length === 0 && (
        <EmptyState icon="📅" title="No timeline data yet" sub="Upload PDFs with dated facts to see the timeline" />
      )}
      <div className="pt-2">
        {entries.map((entry, i) => <TimelineNode key={entry.period} entry={entry} index={i} onOpenFact={onOpenFact} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Extraction Failures view — Task 4.1
// ---------------------------------------------------------------------------
const FAILURE_REASON_LABELS: Record<string, { label: string; color: string }> = {
  low_confidence:       { label: "Low Confidence",       color: "bg-amber-100 text-amber-800 border-amber-200" },
  canonical_value_none: { label: "Unparseable Value",    color: "bg-red-100 text-red-800 border-red-200" },
  unmapped_attribute:   { label: "Unmapped Attribute",   color: "bg-gray-100 text-gray-700 border-gray-200" },
};

function FailureCard({ failure }: { failure: ExtractionFailure }) {
  const [open, setOpen] = useState(false);
  const style = FAILURE_REASON_LABELS[failure.failure_reason] ?? {
    label: failure.failure_reason, color: "bg-gray-100 text-gray-700 border-gray-200",
  };

  return (
    <Card>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded border ${style.color}`}>
                ⚠ {style.label}
              </span>
              <span className="text-xs text-muted-foreground font-mono">
                {failure.original_filename}
                {failure.page_number != null && ` · p.${failure.page_number}`}
              </span>
              <span className="text-xs font-mono text-muted-foreground">
                conf: {Math.round(failure.confidence * 100)}%
              </span>
            </div>
            <p className="text-sm font-mono bg-muted/40 rounded px-2 py-1 truncate">
              {failure.raw_text}
            </p>
          </div>
        </div>

        <button
          onClick={() => setOpen((v) => !v)}
          className="text-xs text-primary hover:underline"
        >
          {open ? "Hide" : "Show"} chain-of-thought
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
              <div className="bg-muted/30 rounded p-3 text-xs text-muted-foreground space-y-1.5 border">
                <p className="font-semibold text-foreground text-[11px] uppercase tracking-wide">Chain of Thought</p>
                {failure.chain_of_thought.split(" — ").map((part, i) => (
                  <p key={i} className="leading-relaxed">
                    {i === 0 ? "🔍 " : i === 1 ? "→ " : "⚠ "}{part}
                  </p>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

function FailuresView({ projectId }: { projectId?: string }) {
  const [reasonFilter, setReasonFilter] = useState("all");
  const { data: failures = [], isLoading } = useExtractionFailures(
    projectId ? { project_id: projectId } : undefined
  );

  const filtered = reasonFilter === "all"
    ? failures
    : failures.filter((f) => f.failure_reason === reasonFilter);

  const counts = failures.reduce<Record<string, number>>((acc, f) => {
    acc[f.failure_reason] = (acc[f.failure_reason] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <p className="text-sm text-muted-foreground">
          {failures.length} flagged extraction{failures.length !== 1 ? "s" : ""}
        </p>
        <div className="flex gap-2 flex-wrap">
          {["all", ...Object.keys(counts)].map((r) => {
            const s = FAILURE_REASON_LABELS[r];
            return (
              <button
                key={r}
                onClick={() => setReasonFilter(r)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  reasonFilter === r
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border hover:border-primary/50"
                }`}
              >
                {r === "all" ? `All (${failures.length})` : `${s?.label ?? r} (${counts[r]})`}
              </button>
            );
          })}
        </div>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

      {!isLoading && failures.length === 0 && (
        <EmptyState
          icon="✅"
          title="No extraction failures logged"
          sub="All extracted facts passed quality checks"
        />
      )}

      <div className="space-y-3">
        {filtered.map((f) => <FailureCard key={f.id} failure={f} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cases view — four required cases with evidence + reasoning
// ---------------------------------------------------------------------------
const CASE_META = [
  {
    key: "corroborated" as const,
    number: "1",
    title: "Corroborated Fact",
    desc: "Same fact confirmed across multiple documents, even if expressed differently.",
    border: "border-l-green-500",
    badge: "bg-green-100 text-green-800",
    icon: "✓",
  },
  {
    key: "contradiction" as const,
    number: "2",
    title: "Genuine Contradiction",
    desc: "Same entity, same attribute, same period — values conflict beyond tolerance.",
    border: "border-l-red-500",
    badge: "bg-red-100 text-red-800",
    icon: "✗",
  },
  {
    key: "reconciled" as const,
    number: "3",
    title: "Apparent Contradiction — Explained by Context",
    desc: "Values differ but the conflict is resolved by period, scope, or accounting standard.",
    border: "border-l-amber-500",
    badge: "bg-amber-100 text-amber-800",
    icon: "⟳",
  },
];

const FAILURE_REASON_LABELS_CASES: Record<string, string> = {
  low_confidence:       "Low Confidence",
  canonical_value_none: "Unparseable Value",
  unmapped_attribute:   "Unmapped Attribute",
};

function CaseFactSide({ fact, label }: { fact: any; label: string }) {
  if (!fact) return <div className="flex-1 text-xs text-muted-foreground italic">No fact data</div>;
  return (
    <div className="flex-1 min-w-0 space-y-1.5">
      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">{label}</p>
      <p className="font-semibold text-sm">{fact.entity}</p>
      <p className="text-xs text-muted-foreground">{fact.attribute}</p>
      <p className="font-mono font-bold text-base">
        {fact.canonical_value || fact.raw_value}
        {fact.unit && <span className="text-xs font-normal text-muted-foreground ml-1">{fact.unit}</span>}
      </p>
      {fact.period && (
        <span className="inline-block text-xs font-mono border rounded px-1.5 py-0.5">{fact.period}</span>
      )}
      <div className="pt-1 space-y-0.5">
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{fact.original_filename}</span>
          {fact.page_number != null && <span className="font-mono"> · p.{fact.page_number}</span>}
        </p>
        {fact.snippet && (
          <p className="text-xs italic text-muted-foreground border-l-2 border-muted pl-2 leading-relaxed line-clamp-3">
            &ldquo;{fact.snippet}&rdquo;
          </p>
        )}
      </div>
    </div>
  );
}

function CaseReasoningChain({ steps }: { steps: Array<{ step: number; check: string; result: string; detail: string }> }) {
  const colors: Record<string, string> = {
    match: "bg-green-100 text-green-800", different: "bg-amber-100 text-amber-800",
    conflict: "bg-red-100 text-red-800",  info: "bg-blue-100 text-blue-800",
    corroborated: "bg-green-100 text-green-800", contradiction: "bg-red-100 text-red-800",
    reconciled: "bg-amber-100 text-amber-800",   flagged: "bg-orange-100 text-orange-800",
    extraction_failure: "bg-red-100 text-red-800",
  };
  return (
    <div className="space-y-2">
      {steps.map((s) => (
        <div key={s.step} className="flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
            {s.step}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold">{s.check}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${colors[s.result] ?? colors.info}`}>
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

function RelationshipCase({ meta, rel }: { meta: typeof CASE_META[number]; rel: any }) {
  const [showReasoning, setShowReasoning] = useState(true);
  return (
    <Card className={`border-l-4 ${meta.border}`}>
      <CardContent className="p-5 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${meta.badge}`}>
                {meta.icon} Case {meta.number}
              </span>
              <span className="font-semibold text-sm">{meta.title}</span>
            </div>
            <p className="text-xs text-muted-foreground">{meta.desc}</p>
          </div>
          <span className="text-xs font-mono text-muted-foreground shrink-0">
            {Math.round(rel.confidence * 100)}% confidence
          </span>
        </div>

        {/* Source evidence side-by-side */}
        <div className="grid grid-cols-2 gap-4 bg-muted/30 rounded-lg p-4">
          <CaseFactSide fact={rel.source_fact} label="Document A" />
          <div className="border-l pl-4">
            <CaseFactSide fact={rel.target_fact} label="Document B" />
          </div>
        </div>

        {/* Explanation */}
        {rel.explanation && (
          <p className="text-xs text-muted-foreground italic border-l-2 border-primary/30 pl-3">
            💡 {rel.explanation}
          </p>
        )}

        {/* Reasoning chain */}
        {rel.reasoning_steps?.length > 0 && (
          <div className="space-y-2">
            <button
              onClick={() => setShowReasoning((v) => !v)}
              className="text-xs font-semibold text-primary hover:underline"
            >
              {showReasoning ? "▲ Hide" : "▼ Show"} step-by-step reasoning
            </button>
            <AnimatePresence>
              {showReasoning && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="bg-muted/20 rounded-lg p-3 border">
                    <CaseReasoningChain steps={rel.reasoning_steps} />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FailureCase({ failure }: { failure: any }) {
  const reasonLabel = FAILURE_REASON_LABELS_CASES[failure.failure_reason] ?? failure.failure_reason;
  return (
    <Card className="border-l-4 border-l-orange-400">
      <CardContent className="p-5 space-y-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-orange-100 text-orange-800">
              ⚠ Case 4
            </span>
            <span className="font-semibold text-sm">Extraction / Reasoning Failure</span>
          </div>
          <p className="text-xs text-muted-foreground">
            A fact that failed quality checks — logged with its chain-of-thought for auditability.
          </p>
        </div>

        <div className="bg-muted/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold px-1.5 py-0.5 rounded border bg-orange-50 text-orange-700 border-orange-200">
              {reasonLabel}
            </span>
            <span className="text-xs font-mono text-muted-foreground">
              {failure.original_filename}
              {failure.page_number != null && ` · p.${failure.page_number}`}
            </span>
            <span className="text-xs font-mono text-muted-foreground">
              conf: {Math.round(failure.confidence * 100)}%
            </span>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Raw text</p>
            <p className="text-sm font-mono bg-background rounded px-2 py-1.5 border">{failure.raw_text}</p>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Chain of Thought</p>
          <div className="bg-muted/20 rounded-lg p-3 border space-y-2">
            {failure.chain_of_thought.split(" — ").map((part: string, i: number) => (
              <p key={i} className="text-xs text-muted-foreground leading-relaxed">
                <span className="font-mono text-foreground">{i === 0 ? "🔍" : i === 1 ? "→" : "⚠"}</span>{" "}{part}
              </p>
            ))}
          </div>
        </div>

        <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-3 border border-blue-200 dark:border-blue-800 space-y-1">
          <p className="text-xs font-semibold text-blue-800 dark:text-blue-300">How it was handled</p>
          <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">
            The fact was stored but flagged in the <code className="font-mono bg-blue-100 dark:bg-blue-900 px-1 rounded">extraction_failures</code> table.
            Low-confidence facts are still surfaced in search but marked for review.
            The relationship engine skips them for contradiction/corroboration classification.
          </p>
          <p className="text-xs font-semibold text-blue-800 dark:text-blue-300 mt-2">What would improve it</p>
          <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">
            Replace <code className="font-mono bg-blue-100 dark:bg-blue-900 px-1 rounded">en_core_web_sm</code> with a finance-domain NER model,
            or inject the document title as a known entity hint before page processing
            (now implemented — see entity hint extraction in the pipeline).
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function CasesView({ projectId }: { projectId?: string }) {
  const { data: cases, isLoading } = useCases(projectId);

  if (isLoading) return (
    <div className="space-y-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="border rounded-xl p-6 h-48 animate-pulse bg-muted/30" />
      ))}
    </div>
  );

  const hasAny = cases && (
    cases.corroborated || cases.contradiction || cases.reconciled || cases.extraction_failure
  );

  if (!hasAny) return (
    <EmptyState
      icon="📋"
      title="No cases yet"
      sub="Upload multiple PDFs to a project — the system will automatically detect and classify all four case types."
    />
  );

  return (
    <div className="space-y-6">
      <div className="bg-muted/30 rounded-xl p-4 border space-y-1">
        <p className="text-sm font-semibold">Four Required Cases</p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Each example below is drawn live from the knowledge layer — no hardcoded data.
          Every fact is linked to its source document and page. Reasoning chains show the exact
          logic used to classify each relationship.
        </p>
      </div>

      {CASE_META.map((meta) => {
        const rel = cases?.[meta.key];
        if (!rel) return (
          <Card key={meta.key} className={`border-l-4 ${meta.border} opacity-50`}>
            <CardContent className="p-5">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${meta.badge}`}>
                  {meta.icon} Case {meta.number}
                </span>
                <span className="text-sm text-muted-foreground">{meta.title} — no example found yet</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Upload more documents to generate this case type.
              </p>
            </CardContent>
          </Card>
        );
        return <RelationshipCase key={meta.key} meta={meta} rel={rel} />;
      })}

      {cases?.extraction_failure
        ? <FailureCase failure={cases.extraction_failure} />
        : (
          <Card className="border-l-4 border-l-orange-400 opacity-50">
            <CardContent className="p-5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-orange-100 text-orange-800">⚠ Case 4</span>
                <span className="text-sm text-muted-foreground">Extraction Failure — no failures logged yet</span>
              </div>
            </CardContent>
          </Card>
        )
      }
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
function ExploreInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { scope } = useScope();

  const viewParam = (searchParams.get("view") as View) || "table";
  const [view, setView] = useState<View>(viewParam);
  const [search, setSearch] = useState("");
  const [openFactId, setOpenFactId] = useState<string | null>(null);

  const projectId = scope.projectId ?? undefined;
  const documentId = scope.documentId ?? undefined;

  const handleViewChange = (v: View) => {
    setView(v);
    const params = new URLSearchParams(searchParams.toString());
    params.set("view", v);
    router.replace(`/explore?${params.toString()}`);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 w-full space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Explore</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          {documentId ? `Viewing: ${scope.documentName}` : projectId ? `Project: ${scope.projectName}` : "All facts across all projects"}
        </p>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        {view === "table" && (
          <Input placeholder="Search entity, attribute, value…" value={search}
            onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        )}
        <div className="flex items-center border rounded-lg overflow-hidden ml-auto">
          {VIEWS.map((v) => (
            <button key={v.id} onClick={() => handleViewChange(v.id)}
              className={`px-4 py-1.5 text-sm font-medium transition-colors
                ${view === v.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted"}`}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={view} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
          {view === "table" && (
            <TableView search={search} projectId={projectId} documentId={documentId} onOpenFact={setOpenFactId} />
          )}
          {view === "graph" && (
            <GraphViewWrapper projectId={projectId} documentId={documentId} onOpenFact={setOpenFactId} />
          )}
          {view === "relationships" && (
            <RelationshipsView projectId={projectId} onOpenFact={setOpenFactId} />
          )}
          {view === "timeline" && (
            <TimelineView projectId={projectId} documentId={documentId} onOpenFact={setOpenFactId} />
          )}
          {view === "failures" && (
            <FailuresView projectId={projectId} />
          )}
          {view === "cases" && (
            <CasesView projectId={projectId} />
          )}
        </motion.div>
      </AnimatePresence>

      <FactDetailPanel factId={openFactId} onClose={() => setOpenFactId(null)} />
    </div>
  );
}

export default function ExplorePage() {
  return (
    <Suspense>
      <ExploreInner />
    </Suspense>
  );
}
