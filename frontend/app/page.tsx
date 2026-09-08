"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Card, CardContent } from "@/components/ui/card";
import { useFactStats } from "@/hooks/useFacts";

const STATS = [
  { key: "documents",          label: "Documents",      icon: "📄", href: "/upload" },
  { key: "facts",              label: "Facts Extracted", icon: "⬡",  href: "/facts" },
  { key: "corroborated",       label: "Corroborated",   icon: "✓",  href: "/relationships" },
  { key: "contradictions",     label: "Contradictions", icon: "✗",  href: "/relationships" },
  { key: "reconciled",         label: "Reconciled",     icon: "⟳",  href: "/relationships" },
];

const STEPS = [
  {
    step: "1",
    icon: "📄",
    title: "Upload PDFs",
    desc: "Drop one or more PDFs. Facts are extracted automatically — no setup needed.",
    href: "/upload",
    cta: "Upload",
  },
  {
    step: "2",
    icon: "⬡",
    title: "Explore Facts",
    desc: "Every extracted fact is linked to its source page and sentence. Search by entity, attribute, or value.",
    href: "/facts",
    cta: "Browse Facts",
  },
  {
    step: "3",
    icon: "🔗",
    title: "See Relationships",
    desc: "Facts across documents are compared. Corroborations, contradictions, and reconciliations are detected automatically.",
    href: "/relationships",
    cta: "View Relationships",
  },
  {
    step: "4",
    icon: "💬",
    title: "Ask Questions",
    desc: "Ask anything about your documents. Every answer is grounded in extracted facts with source citations.",
    href: "/chat",
    cta: "Open Chat",
  },
];

export default function HomePage() {
  const { data: stats, isLoading } = useFactStats();
  const hasData = !isLoading && (stats as any)?.documents > 0;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />
      <main className="flex-1 max-w-4xl mx-auto px-4 py-12 w-full space-y-12">

        {/* Hero */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-4xl font-bold tracking-tight mb-3">
            FactForge
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl leading-relaxed">
            Upload PDFs. Every fact is extracted, grounded in its source, and compared across documents —
            corroborations, contradictions, and reconciliations included.
          </p>
        </motion.div>

        {/* Stats — only shown when there's data */}
        {hasData && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-2 sm:grid-cols-5 gap-3"
          >
            {STATS.map((s) => (
              <Link key={s.key} href={s.href}>
                <Card className="hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer">
                  <CardContent className="p-4 text-center">
                    <div className="text-xl mb-1">{s.icon}</div>
                    <div className="text-2xl font-bold tabular-nums">
                      {(stats as any)?.[s.key] ?? 0}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </motion.div>
        )}

        {/* Workflow steps */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-3"
        >
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            How it works
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {STEPS.map((s, i) => (
              <motion.div
                key={s.step}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.07 }}
              >
                <Link href={s.href}>
                  <Card className="h-full hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer group">
                    <CardContent className="p-5 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0">
                          {s.step}
                        </span>
                        <span className="text-base">{s.icon}</span>
                        <span className="font-semibold text-sm group-hover:text-primary transition-colors">
                          {s.title}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">{s.desc}</p>
                      <p className="text-xs text-primary font-medium">{s.cta} →</p>
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* What gets detected */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="space-y-3"
        >
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            What gets detected
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              {
                icon: "✓",
                color: "text-green-600 bg-green-50",
                title: "Corroborated",
                desc: "Same fact confirmed by multiple documents — same entity, attribute, period, and value within tolerance.",
              },
              {
                icon: "✗",
                color: "text-red-600 bg-red-50",
                title: "Contradiction",
                desc: "Same entity and attribute, same period, but conflicting values across documents.",
              },
              {
                icon: "⟳",
                color: "text-amber-600 bg-amber-50",
                title: "Reconciled",
                desc: "Values that look contradictory but cover different time periods — temporal change, not a conflict.",
              },
            ].map((item) => (
              <Card key={item.title} className="border-border/60">
                <CardContent className="p-4 space-y-2">
                  <span className={`inline-flex w-7 h-7 rounded-full items-center justify-center text-sm font-bold ${item.color}`}>
                    {item.icon}
                  </span>
                  <p className="font-semibold text-sm">{item.title}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </motion.div>

      </main>
    </div>
  );
}
