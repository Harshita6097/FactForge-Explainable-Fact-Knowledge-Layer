"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/navbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useFact } from "@/hooks/useFacts";
import { useFactRelationships } from "@/hooks/useRelationships";

const TYPE_STYLES: Record<string, { badge: string; label: string }> = {
  corroborated: { badge: "bg-green-100 text-green-800", label: "✓ Corroborated" },
  contradiction: { badge: "bg-red-100 text-red-800", label: "✗ Contradiction" },
  reconciled:    { badge: "bg-amber-100 text-amber-800", label: "⟳ Reconciled" },
  related:       { badge: "bg-blue-100 text-blue-800", label: "~ Related" },
};

function confidenceVariant(c: number): "default" | "secondary" | "destructive" {
  if (c >= 0.8) return "default";
  if (c >= 0.6) return "secondary";
  return "destructive";
}

export default function FactDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: fact, isLoading } = useFact(id);
  const { data: relationships = [] } = useFactRelationships(id);

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
              {fact.unit && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Unit</p>
                  <p className="font-medium">{fact.unit}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Evidence panel */}
        <div className="space-y-3">
          <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
            Evidence ({fact.evidence?.length ?? 0})
          </h2>
          {fact.evidence?.length === 0 && (
            <p className="text-sm text-muted-foreground">No evidence linked.</p>
          )}
          {fact.evidence?.map((ev) => (
            <Card key={ev.id} className="border-l-4 border-l-primary">
              <CardContent className="p-4 space-y-2">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{ev.document_name}</span>
                  <span>·</span>
                  <span>Page {ev.page_number}</span>
                </div>
                <Separator />
                <blockquote className="text-sm italic text-muted-foreground border-l-2 border-muted pl-3">
                  "{ev.snippet}"
                </blockquote>
              </CardContent>
            </Card>
          ))}
        </div>
        {/* Relationships panel */}
        {relationships.length > 0 && (
          <div className="space-y-3">
            <h2 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground">
              Relationships ({relationships.length})
            </h2>
            {relationships.map((rel: any) => {
              const other = rel.source_fact_id === id ? rel.target_fact : rel.source_fact;
              const style = TYPE_STYLES[rel.relationship_type] ?? TYPE_STYLES.related;
              return (
                <Card key={rel.id}>
                  <CardContent className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
                        {style.label}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {Math.round(rel.confidence * 100)}% confidence
                      </span>
                    </div>
                    {other && (
                      <div className="text-sm">
                        <span className="font-medium">{other.entity}</span>
                        <span className="text-muted-foreground"> · {other.attribute}</span>
                        <span className="ml-2">{other.canonical_value || other.raw_value}</span>
                        {other.period && <Badge variant="outline" className="ml-2 text-xs">{other.period}</Badge>}
                      </div>
                    )}
                    {rel.explanation && (
                      <p className="text-xs text-muted-foreground italic">💡 {rel.explanation}</p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
