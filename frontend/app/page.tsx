"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useFactStats } from "@/hooks/useFacts";

const STAT_CONFIG = [
  { key: "documents", label: "PDFs Uploaded", href: "/upload", icon: "📄", color: "text-blue-600" },
  { key: "canonical_facts", label: "Canonical Facts", href: "/facts", icon: "⬡", color: "text-violet-600" },
  { key: "multi_document_facts", label: "Cross-Doc Facts", href: "/facts", icon: "🔗", color: "text-indigo-600" },
  { key: "corroborated", label: "Corroborated", href: "/relationships", icon: "✓", color: "text-green-600" },
  { key: "contradictions", label: "Contradictions", href: "/relationships", icon: "✗", color: "text-red-600" },
  { key: "reconciled", label: "Reconciled", href: "/relationships", icon: "⟳", color: "text-amber-600" },
];

function StatCard({
  label, value, href, icon, color, delay,
}: {
  label: string; value: number; href: string; icon: string; color: string; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
    >
      <Link href={href}>
        <Card className="hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer group">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
              <span className={color}>{icon}</span>
              {label}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <p className="text-3xl font-bold tabular-nums group-hover:text-primary transition-colors">
              {value.toLocaleString()}
            </p>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}

const QUICK_LINKS = [
  { href: "/upload", label: "Upload PDFs", variant: "primary" as const },
  { href: "/facts", label: "Explore Knowledge", variant: "outline" as const },
  { href: "/relationships", label: "View Relationships", variant: "outline" as const },
  { href: "/chat", label: "Ask a Question", variant: "outline" as const },
];

export default function HomePage() {
  const { data: stats, isLoading } = useFactStats();

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto px-4 py-12 w-full">

        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl text-primary">⬡</span>
            <Badge variant="secondary" className="text-xs font-medium">Explainable Fact Intelligence</Badge>
          </div>
          <h1 className="text-4xl font-bold tracking-tight mb-2">
            Every fact. Every source. Every relationship.
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl">
            FactForge transforms PDFs into a structured knowledge layer where every extracted fact
            is a first-class object — with identity, evidence, confidence, and cross-document reasoning.
          </p>
        </motion.div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-10">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="p-4 h-24" />
                </Card>
              ))
            : STAT_CONFIG.map((s, i) => (
                <StatCard
                  key={s.key}
                  label={s.label}
                  value={(stats as any)?.[s.key] ?? 0}
                  href={s.href}
                  icon={s.icon}
                  color={s.color}
                  delay={i * 0.05}
                />
              ))}
        </div>

        {/* Quick actions */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="flex flex-wrap gap-3 mb-12"
        >
          {QUICK_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={
                l.variant === "primary"
                  ? "inline-flex items-center gap-2 bg-primary text-primary-foreground px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm"
                  : "inline-flex items-center gap-2 border border-border px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-muted transition-colors"
              }
            >
              {l.label}
            </Link>
          ))}
        </motion.div>

        {/* What makes this different */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
        >
          {[
            {
              icon: "⬡",
              title: "Canonical Facts",
              desc: "Equivalent facts from multiple documents are merged into single canonical objects with aggregated evidence.",
            },
            {
              icon: "🔍",
              title: "Explainable Relationships",
              desc: "Every corroboration, contradiction, and reconciliation includes a step-by-step reasoning chain.",
            },
            {
              icon: "💬",
              title: "Grounded Answers",
              desc: "Chat answers are built from the knowledge layer — every claim is backed by a specific fact and source.",
            },
          ].map((item) => (
            <Card key={item.title} className="border-border/60">
              <CardContent className="p-5">
                <div className="text-2xl mb-3">{item.icon}</div>
                <h3 className="font-semibold mb-1">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </CardContent>
            </Card>
          ))}
        </motion.div>
      </main>
    </div>
  );
}
