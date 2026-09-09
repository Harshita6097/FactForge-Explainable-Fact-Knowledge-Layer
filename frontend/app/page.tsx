"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { useProjects } from "@/hooks/useProjects";
import { useScope } from "@/contexts/ScopeContext";
import { useProjectStats } from "@/hooks/useProjects";
import { UploadSheet } from "@/components/upload-sheet";
import { useState } from "react";

const STEPS = [
  { step: "1", icon: "📁", title: "Create a Project", desc: "Name your research topic or document set. Each project is an isolated knowledge workspace.", href: null,               cta: "Create project", action: "new-project" },
  { step: "2", icon: "📄", title: "Upload PDFs",      desc: "Drop PDFs into the project. Facts are extracted automatically — no setup needed.",          href: null,               cta: "Upload",         action: "upload" },
  { step: "3", icon: "⬡",  title: "Explore Facts",   desc: "Every fact is linked to its source page. Search, filter, and view the relationship graph.",  href: "/explore?view=graph", cta: "Open Graph",    action: null },
  { step: "4", icon: "💬", title: "Ask Questions",   desc: "Chat is scoped to your project. Every answer is grounded in extracted facts with citations.", href: "/chat",           cta: "Open Chat",     action: null },
];

function ProjectStats({ projectId }: { projectId: string }) {
  const { data: stats } = useProjectStats(projectId);
  if (!stats) return null;
  const items = [
    { label: "Documents",    value: stats.documents,      icon: "📄" },
    { label: "Facts",        value: stats.facts,          icon: "⬡"  },
    { label: "Corroborated", value: stats.corroborated,   icon: "✓"  },
    { label: "Contradictions", value: stats.contradictions, icon: "✗" },
  ];
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
      className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {items.map((s) => (
        <Card key={s.label} className="hover:border-primary/40 transition-all">
          <CardContent className="p-4 text-center">
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="text-2xl font-bold tabular-nums font-mono">{s.value}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
          </CardContent>
        </Card>
      ))}
    </motion.div>
  );
}

export default function HomePage() {
  const { data: projects = [] } = useProjects();
  const { scope } = useScope();
  const [uploadOpen, setUploadOpen] = useState(false);
  const hasProjects = projects.length > 0;

  const handleStepClick = (action: string | null) => {
    if (action === "new-project") {
      // Dispatch a custom event the sidebar listens to
      window.dispatchEvent(new CustomEvent("factforge:new-project"));
    } else if (action === "upload") {
      if (scope.projectId) {
        setUploadOpen(true);
      } else {
        // No project selected — prompt user to create/select one first
        window.dispatchEvent(new CustomEvent("factforge:new-project"));
      }
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-12 w-full space-y-12">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-4xl font-bold tracking-tight mb-3">FactForge</h1>
        <p className="text-muted-foreground text-lg max-w-2xl leading-relaxed">
          Organise your PDFs into projects. Every fact is extracted, grounded in its source, and compared across documents within the same project.
        </p>
      </motion.div>

      {scope.projectId && <ProjectStats projectId={scope.projectId} />}

      {!hasProjects && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="border-2 border-dashed rounded-xl p-10 text-center space-y-3">
          <p className="text-4xl">📁</p>
          <p className="font-semibold text-lg">No projects yet</p>
          <p className="text-muted-foreground text-sm">Create your first project using the sidebar to get started.</p>
        </motion.div>
      )}

      {hasProjects && !scope.projectId && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="border rounded-xl p-6 bg-muted/30 space-y-2">
          <p className="font-semibold text-sm">Select a project</p>
          <p className="text-xs text-muted-foreground">Click a project in the sidebar to scope all views to it.</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {projects.map((p) => (
              <Link key={p.id} href="/explore"
                className="text-xs border rounded-full px-3 py-1 hover:bg-accent transition-colors">
                {p.name} · {p.fact_count}f
              </Link>
            ))}
          </div>
        </motion.div>
      )}

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="space-y-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">How it works</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {STEPS.map((s, i) => {
            const inner = (
              <Card className="h-full hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer group">
                <CardContent className="p-5 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0">{s.step}</span>
                    <span className="text-base">{s.icon}</span>
                    <span className="font-semibold text-sm group-hover:text-primary transition-colors">{s.title}</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{s.desc}</p>
                  <p className="text-xs text-primary font-medium">{s.cta} →</p>
                </CardContent>
              </Card>
            );
            return (
              <motion.div key={s.step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.07 }}>
                {s.action ? (
                  <div onClick={() => handleStepClick(s.action)}>{inner}</div>
                ) : (
                  <Link href={s.href!}>{inner}</Link>
                )}
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {uploadOpen && scope.projectId && (
        <UploadSheet open={uploadOpen} onClose={() => setUploadOpen(false)} projectId={scope.projectId} />
      )}
    </div>
  );
}
