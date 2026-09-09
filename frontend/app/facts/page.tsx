"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useFacts } from "@/hooks/useFacts";
import { useDocuments } from "@/hooks/useDocuments";
import { useFactRelationships } from "@/hooks/useRelationships";
import { FactDetailPanel, REL_STYLES } from "@/components/fact-detail-panel";
import { Fact } from "@/types";

function RelBadges({ factId }: { factId: string }) {
  const { data: rels = [] } = useFactRelationships(factId);
  if (!rels.length) return null;
  const counts = rels.reduce<Record<string, number>>((acc, r) => {
    acc[r.relationship_type] = (acc[r.relationship_type] ?? 0) + 1;
    return acc;
  }, {});
  return (
    <div className="flex gap-1 flex-wrap mt-1.5">
      {Object.entries(counts).map(([type, count]) => {
        const s = REL_STYLES[type] ?? REL_STYLES.related;
        return (
          <span key={type} className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${s.badge}`}>
            {s.icon} {count} {s.label}
          </span>
        );
      })}
    </div>
  );
}

function FactCard({ fact, onSelect }: { fact: Fact; onSelect: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="border rounded-lg p-4 hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer"
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{fact.entity}</span>
            <span>·</span>
            <span>{fact.attribute}</span>
            {fact.period && (
              <Badge variant="outline" className="text-xs">{fact.period}</Badge>
            )}
          </div>
          <p className="text-lg font-bold">
            {fact.canonical_value || fact.raw_value}
            {(fact.canonical_unit || fact.unit) && (
              <span className="text-sm font-normal text-muted-foreground ml-1">
                {fact.canonical_unit || fact.unit}
              </span>
            )}
          </p>
          <RelBadges factId={fact.id} />
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <div className={`text-sm font-bold ${
            fact.confidence >= 0.8 ? "text-green-600" :
            fact.confidence >= 0.6 ? "text-amber-600" : "text-red-500"
          }`}>
            {Math.round(fact.confidence * 100)}%
          </div>
          <div className="text-xs text-muted-foreground">confidence</div>
          <button
            onClick={(e) => { e.stopPropagation(); onSelect(fact.id); }}
            className="text-[11px] text-primary hover:underline mt-1"
          >
            Details →
          </button>
        </div>
      </div>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="mt-3 pt-3 border-t space-y-1.5"
        >
          {(fact as any).evidence?.map((ev: any, i: number) => (
            <div key={i} className="space-y-1">
              <p className="text-xs text-muted-foreground">
                📄 <span className="font-medium text-foreground">{ev.document_name || ev.original_filename}</span>
                {ev.page_number && <span> · Page {ev.page_number}</span>}
              </p>
              {ev.snippet && (
                <p className="text-xs italic text-muted-foreground border-l-2 border-muted pl-2 leading-relaxed">
                  &ldquo;{ev.snippet}&rdquo;
                </p>
              )}
            </div>
          ))}
          {!(fact as any).evidence?.length && (
            <p className="text-xs text-muted-foreground">No evidence available</p>
          )}
        </motion.div>
      )}
    </div>
  );
}

export default function FactsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [selectedDoc, setSelectedDoc] = useState(searchParams.get("doc") || "");
  const [selectedFactId, setSelectedFactId] = useState<string | null>(null);

  const { data: documents = [] } = useDocuments();
  const { data: facts = [], isLoading } = useFacts(
    selectedDoc ? { document_id: selectedDoc } : undefined
  );

  const filtered = facts.filter((f) => {
    const q = search.toLowerCase();
    return !q ||
      f.entity.toLowerCase().includes(q) ||
      f.attribute.toLowerCase().includes(q) ||
      f.raw_value.toLowerCase().includes(q) ||
      (f.period?.toLowerCase().includes(q) ?? false);
  });

  // Group by attribute
  const grouped = filtered.reduce<Record<string, Fact[]>>((acc, f) => {
    const key = f.attribute || "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(f);
    return acc;
  }, {});

  const completedDocs = documents.filter((d) => d.status === "completed");

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <FactDetailPanel factId={selectedFactId} onClose={() => setSelectedFactId(null)} />
      <main className="flex-1 max-w-4xl mx-auto px-4 py-10 w-full space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold">Facts</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Every fact is linked to its source document and page. Click any fact to see the evidence.
          </p>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          {/* Document filter */}
          <select
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            className="text-sm border rounded-md px-3 py-2 bg-background hover:border-primary/50 transition-colors min-w-[200px]"
          >
            <option value="">All documents</option>
            {completedDocs.map((d) => (
              <option key={d.id} value={d.id}>{d.original_filename}</option>
            ))}
          </select>

          <Input
            placeholder="Search entity, attribute, value…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />

          <span className="text-xs text-muted-foreground self-center">
            {filtered.length} fact{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="border rounded-lg p-4 h-20 animate-pulse bg-muted/30" />
            ))}
          </div>
        )}

        {/* Empty */}
        {!isLoading && facts.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-3xl mb-3">⬡</p>
            <p className="font-medium text-sm">No facts yet</p>
            <p className="text-xs mt-1">
              <button onClick={() => router.push("/upload")} className="text-primary hover:underline">
                Upload a PDF
              </button>{" "}
              to extract facts
            </p>
          </div>
        )}

        {/* Grouped facts */}
        {!isLoading && Object.keys(grouped).length > 0 && (
          <div className="space-y-6">
            {Object.entries(grouped)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([attribute, attrFacts]) => (
                <motion.div
                  key={attribute}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      {attribute}
                    </p>
                    <span className="text-xs text-muted-foreground">({attrFacts.length})</span>
                  </div>
                  <div className="space-y-2">
                    {attrFacts.map((fact) => (
                      <FactCard key={fact.id} fact={fact} onSelect={setSelectedFactId} />
                    ))}
                  </div>
                </motion.div>
              ))}
          </div>
        )}

        {!isLoading && facts.length > 0 && filtered.length === 0 && (
          <p className="text-muted-foreground text-sm text-center py-8">
            No facts match your search.
          </p>
        )}
      </main>
    </div>
  );
}
