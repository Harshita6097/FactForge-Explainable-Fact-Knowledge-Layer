"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCanonicalFacts } from "@/hooks/useKnowledge";
import { useFacts } from "@/hooks/useFacts";
import { CanonicalFact, Fact } from "@/types";

// ---------------------------------------------------------------------------
// Canonical Fact Card — primary view
// ---------------------------------------------------------------------------
function CanonicalFactCard({ cf, onClick }: { cf: CanonicalFact; onClick: () => void }) {
  const hasConflict = cf.conflicting_count > 0;
  const isMultiDoc = cf.supporting_count > 1;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -1 }}
      onClick={onClick}
      className="cursor-pointer"
    >
      <Card className={`hover:shadow-md transition-all border ${hasConflict ? "border-red-200 dark:border-red-900" : "hover:border-primary/40"}`}>
        <CardContent className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1 space-y-2">
              {/* Entity + Attribute */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-semibold text-primary uppercase tracking-wide">
                  {cf.canonical_entity}
                </span>
                <span className="text-muted-foreground text-xs">·</span>
                <span className="text-sm text-muted-foreground">{cf.canonical_attribute}</span>
                {cf.period && (
                  <Badge variant="outline" className="text-xs">{cf.period}</Badge>
                )}
              </div>

              {/* Value */}
              <p className="text-xl font-bold">
                {cf.canonical_value || "—"}
                {cf.canonical_unit && (
                  <span className="text-sm font-normal text-muted-foreground ml-1.5">
                    {cf.canonical_unit}
                  </span>
                )}
              </p>

              {/* Support indicators */}
              <div className="flex items-center gap-2 flex-wrap">
                {isMultiDoc && (
                  <span className="text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-950 px-2 py-0.5 rounded-full font-medium">
                    ✓ {cf.supporting_count} documents
                  </span>
                )}
                {hasConflict && (
                  <span className="text-xs text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950 px-2 py-0.5 rounded-full font-medium">
                    ✗ {cf.conflicting_count} conflict{cf.conflicting_count !== 1 ? "s" : ""}
                  </span>
                )}
                {cf.corroboration_count > 0 && (
                  <span className="text-xs text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950 px-2 py-0.5 rounded-full font-medium">
                    ~ {cf.corroboration_count} corroborated
                  </span>
                )}
              </div>
            </div>

            {/* Confidence */}
            <div className="text-right shrink-0">
              <div className={`text-lg font-bold tabular-nums ${
                cf.confidence >= 0.8 ? "text-green-600" :
                cf.confidence >= 0.6 ? "text-amber-600" : "text-red-500"
              }`}>
                {Math.round(cf.confidence * 100)}%
              </div>
              <div className="text-xs text-muted-foreground">confidence</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Raw Fact Card — secondary view
// ---------------------------------------------------------------------------
function RawFactCard({ fact, onClick }: { fact: Fact; onClick: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -1 }}
      onClick={onClick}
      className="cursor-pointer"
    >
      <Card className="hover:border-primary/40 hover:shadow-sm transition-all">
        <CardContent className="p-4 flex items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-sm">{fact.entity}</span>
              <span className="text-muted-foreground text-xs">·</span>
              <span className="text-sm text-muted-foreground">{fact.attribute}</span>
              {fact.period && (
                <Badge variant="outline" className="text-xs">{fact.period}</Badge>
              )}
            </div>
            <p className="text-base font-medium">
              {fact.canonical_value || fact.raw_value}
              {fact.unit && <span className="text-muted-foreground text-sm ml-1">{fact.unit}</span>}
            </p>
          </div>
          <Badge
            variant={fact.confidence >= 0.8 ? "default" : fact.confidence >= 0.6 ? "secondary" : "destructive"}
            className="shrink-0 text-xs"
          >
            {Math.round(fact.confidence * 100)}%
          </Badge>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function FactsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"canonical" | "raw">("canonical");

  const { data: canonicalFacts = [], isLoading: cfLoading } = useCanonicalFacts();
  const { data: rawFacts = [], isLoading: rawLoading } = useFacts();

  const isLoading = view === "canonical" ? cfLoading : rawLoading;

  const filteredCanonical = canonicalFacts.filter((cf) => {
    const q = search.toLowerCase();
    return !q ||
      cf.canonical_entity.toLowerCase().includes(q) ||
      cf.canonical_attribute.toLowerCase().includes(q) ||
      (cf.canonical_value?.toLowerCase().includes(q) ?? false) ||
      (cf.period?.toLowerCase().includes(q) ?? false);
  });

  const filteredRaw = rawFacts.filter((f) => {
    const q = search.toLowerCase();
    return !q ||
      f.entity.toLowerCase().includes(q) ||
      f.attribute.toLowerCase().includes(q) ||
      f.raw_value.toLowerCase().includes(q) ||
      (f.period?.toLowerCase().includes(q) ?? false);
  });

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-5xl mx-auto px-4 py-10 w-full space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold">Knowledge Explorer</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              {view === "canonical"
                ? `${canonicalFacts.length} canonical facts — merged across all documents`
                : `${rawFacts.length} raw facts extracted from documents`}
            </p>
          </div>
          <Input
            placeholder="Search entity, attribute, value…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>

        {/* View toggle */}
        <Tabs value={view} onValueChange={(v) => setView(v as "canonical" | "raw")}>
          <TabsList>
            <TabsTrigger value="canonical">
              ⬡ Canonical Facts
              <span className="ml-1.5 text-xs opacity-70">({canonicalFacts.length})</span>
            </TabsTrigger>
            <TabsTrigger value="raw">
              Raw Facts
              <span className="ml-1.5 text-xs opacity-70">({rawFacts.length})</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-5 h-24" />
              </Card>
            ))}
          </div>
        )}

        {!isLoading && view === "canonical" && canonicalFacts.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-4xl mb-3">⬡</p>
            <p className="font-medium">No canonical facts yet</p>
            <p className="text-sm mt-1">Upload PDFs to build the knowledge layer</p>
          </div>
        )}

        <AnimatePresence mode="wait">
          {view === "canonical" ? (
            <motion.div key="canonical" className="space-y-3">
              {filteredCanonical.map((cf) => (
                <CanonicalFactCard
                  key={cf.id}
                  cf={cf}
                  onClick={() => router.push(`/facts/canonical/${cf.id}`)}
                />
              ))}
            </motion.div>
          ) : (
            <motion.div key="raw" className="space-y-3">
              {filteredRaw.map((fact) => (
                <RawFactCard
                  key={fact.id}
                  fact={fact}
                  onClick={() => router.push(`/facts/${fact.id}`)}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {!isLoading && view === "canonical" && canonicalFacts.length > 0 && filteredCanonical.length === 0 && (
          <p className="text-muted-foreground text-sm text-center py-8">No facts match your search.</p>
        )}
      </main>
    </div>
  );
}
