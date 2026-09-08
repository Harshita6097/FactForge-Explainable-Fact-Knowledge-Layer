"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useFacts } from "@/hooks/useFacts";
import { Fact } from "@/types";

function confidenceVariant(c: number): "default" | "secondary" | "destructive" {
  if (c >= 0.8) return "default";
  if (c >= 0.6) return "secondary";
  return "destructive";
}

function FactCard({ fact, onClick }: { fact: Fact; onClick: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.005 }}
      onClick={onClick}
      className="cursor-pointer"
    >
      <Card className="hover:border-primary/50 transition-colors">
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
          <Badge variant={confidenceVariant(fact.confidence)} className="shrink-0 text-xs">
            {Math.round(fact.confidence * 100)}%
          </Badge>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function FactsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { data: facts = [], isLoading } = useFacts();

  const filtered = facts.filter((f) => {
    const q = search.toLowerCase();
    return (
      !q ||
      f.entity.toLowerCase().includes(q) ||
      f.attribute.toLowerCase().includes(q) ||
      f.raw_value.toLowerCase().includes(q) ||
      (f.period?.toLowerCase().includes(q) ?? false)
    );
  });

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-4xl mx-auto px-4 py-10 w-full space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Fact Explorer</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              {facts.length} facts extracted · click any fact to see evidence
            </p>
          </div>
          <Input
            placeholder="Search entity, attribute, value…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>

        {isLoading && (
          <div className="text-muted-foreground text-sm">Loading facts…</div>
        )}

        {!isLoading && facts.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-4xl mb-3">🔍</p>
            <p className="font-medium">No facts yet</p>
            <p className="text-sm mt-1">Upload a PDF to start extracting facts</p>
          </div>
        )}

        <AnimatePresence>
          <div className="space-y-3">
            {filtered.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                onClick={() => router.push(`/facts/${fact.id}`)}
              />
            ))}
          </div>
        </AnimatePresence>

        {!isLoading && facts.length > 0 && filtered.length === 0 && (
          <p className="text-muted-foreground text-sm text-center py-8">
            No facts match your search.
          </p>
        )}
      </main>
    </div>
  );
}
