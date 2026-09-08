"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useTimeline } from "@/hooks/useTimeline";
import { TimelineEntry, TimelineFact } from "@/lib/api/timeline";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function periodIcon(type: TimelineEntry["period_type"]) {
  switch (type) {
    case "quarter":      return "📊";
    case "fiscal_year":  return "📅";
    case "calendar_year": return "🗓️";
    default:             return "📌";
  }
}

function RelMarkers({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {entry.has_contradiction && (
        <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200 font-medium">
          ✗ Contradiction
        </span>
      )}
      {entry.has_corroboration && (
        <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200 font-medium">
          ✓ Corroborated
        </span>
      )}
      {entry.has_reconciled && (
        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200 font-medium">
          ⟳ Reconciled
        </span>
      )}
    </div>
  );
}

function FactRow({ fact }: { fact: TimelineFact }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="border-l-2 border-border pl-3 py-1 cursor-pointer hover:border-primary/50 transition-colors"
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="text-xs font-semibold text-muted-foreground">{fact.entity}</span>
          <span className="text-xs text-muted-foreground mx-1">·</span>
          <span className="text-xs text-muted-foreground">{fact.attribute}</span>
          <p className="text-sm font-medium mt-0.5">
            {fact.canonical_value || fact.raw_value}
            {fact.unit && <span className="text-muted-foreground text-xs ml-1">{fact.unit}</span>}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {fact.relationships.includes("contradiction") && (
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" title="Contradiction" />
          )}
          {fact.relationships.includes("corroborated") && (
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" title="Corroborated" />
          )}
          {fact.relationships.includes("reconciled") && (
            <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" title="Reconciled" />
          )}
          <Badge variant="outline" className="text-xs">
            {Math.round(fact.confidence * 100)}%
          </Badge>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 space-y-1 overflow-hidden"
          >
            <p className="text-xs text-muted-foreground">
              📄 {fact.document}{fact.page_number ? ` · p.${fact.page_number}` : ""}
            </p>
            {fact.snippet && (
              <p className="text-xs italic text-muted-foreground border-l-2 border-muted pl-2">
                "{fact.snippet}"
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TimelineNode({ entry, index }: { entry: TimelineEntry; index: number }) {
  const [open, setOpen] = useState(index < 3);

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      className="flex gap-4"
    >
      {/* Spine */}
      <div className="flex flex-col items-center">
        <div
          className={`w-3 h-3 rounded-full border-2 mt-1 shrink-0 cursor-pointer transition-colors
            ${entry.has_contradiction
              ? "border-red-500 bg-red-100"
              : entry.has_corroboration
              ? "border-green-500 bg-green-100"
              : "border-primary bg-primary/10"
            }`}
          onClick={() => setOpen((v) => !v)}
        />
        <div className="w-px flex-1 bg-border mt-1" />
      </div>

      {/* Content */}
      <div className="pb-8 flex-1 min-w-0">
        <div
          className="flex items-center gap-2 mb-2 cursor-pointer select-none"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="text-base">{periodIcon(entry.period_type)}</span>
          <span className="font-semibold">{entry.period}</span>
          <Badge variant="secondary" className="text-xs">{entry.fact_count} facts</Badge>
          <RelMarkers entry={entry} />
          <span className="ml-auto text-xs text-muted-foreground">{open ? "▲" : "▼"}</span>
        </div>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <Card>
                <CardContent className="p-4 space-y-3">
                  {entry.facts.map((fact) => (
                    <FactRow key={fact.id} fact={fact} />
                  ))}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TimelinePage() {
  const [entity, setEntity] = useState("");
  const [attribute, setAttribute] = useState("");

  const { data, isLoading } = useTimeline({
    entity: entity || undefined,
    attribute: attribute || undefined,
  });

  const entries = data?.entries ?? [];

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-4xl mx-auto px-4 py-10 w-full space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Timeline</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data
              ? `${data.total_periods} periods · ${data.total_facts} facts`
              : "Chronological view of all extracted facts"}
          </p>
        </div>

        {/* Filters */}
        <div className="flex gap-3">
          <Input
            placeholder="Filter by entity…"
            value={entity}
            onChange={(e) => setEntity(e.target.value)}
            className="max-w-xs"
          />
          <Input
            placeholder="Filter by attribute…"
            value={attribute}
            onChange={(e) => setAttribute(e.target.value)}
            className="max-w-xs"
          />
        </div>

        {/* Legend */}
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> Corroborated
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> Contradiction
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Reconciled
          </span>
          <span className="flex items-center gap-1.5 ml-2 text-muted-foreground">
            Click any fact row to see its source evidence
          </span>
        </div>

        {isLoading && (
          <p className="text-muted-foreground text-sm">Building timeline…</p>
        )}

        {!isLoading && entries.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-4xl mb-3">📅</p>
            <p className="font-medium">No timeline data yet</p>
            <p className="text-sm mt-1">
              Upload PDFs with dated facts to see the timeline
            </p>
          </div>
        )}

        {/* Timeline */}
        <div className="pt-2">
          {entries.map((entry, i) => (
            <TimelineNode key={entry.period} entry={entry} index={i} />
          ))}
        </div>
      </main>
    </div>
  );
}
