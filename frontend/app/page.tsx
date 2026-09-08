"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useFactStats } from "@/hooks/useFacts";

function StatCard({ label, value, href }: { label: string; value: number; href?: string }) {
  const content = (
    <Card className="hover:border-primary/50 transition-colors">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}

export default function HomePage() {
  const { data: stats, isLoading } = useFactStats();

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto px-4 py-12 w-full">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <h1 className="text-3xl font-bold tracking-tight">FactForge</h1>
          <p className="text-muted-foreground mt-1 max-w-xl">
            Upload PDFs and explore every extracted fact — with source evidence, confidence scores,
            and cross-document relationships.
          </p>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-10">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-6 h-24" />
              </Card>
            ))
          ) : (
            <>
              <StatCard label="PDFs Uploaded" value={stats?.documents ?? 0} href="/upload" />
              <StatCard label="Facts Extracted" value={stats?.facts ?? 0} href="/facts" />
              <StatCard label="Corroborated" value={stats?.corroborated ?? 0} href="/relationships" />
              <StatCard label="Contradictions" value={stats?.contradictions ?? 0} href="/relationships" />
              <StatCard label="Reconciled" value={stats?.reconciled ?? 0} href="/relationships" />
            </>
          )}
        </div>

        <div className="flex gap-3">
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Upload PDFs
          </Link>
          <Link
            href="/facts"
            className="inline-flex items-center gap-2 border border-border px-4 py-2 rounded-md text-sm font-medium hover:bg-muted transition-colors"
          >
            Explore Facts
          </Link>
        </div>
      </main>
    </div>
  );
}
