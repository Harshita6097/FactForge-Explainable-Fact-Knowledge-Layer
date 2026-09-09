"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useProjects, useCreateProject, useDeleteProject } from "@/hooks/useProjects";
import { useDocuments, useDeleteDocument } from "@/hooks/useDocuments";
import { useScope } from "@/contexts/ScopeContext";
import { UploadSheet } from "@/components/upload-sheet";
import { Project, Document } from "@/types";

const STATUS_DOT: Record<string, string> = {
  pending: "bg-gray-400", processing: "bg-blue-500", extracted: "bg-blue-500",
  mining: "bg-violet-500", analyzing: "bg-amber-500", completed: "bg-green-500", failed: "bg-red-500",
};

// ---------------------------------------------------------------------------
// New project inline form
// ---------------------------------------------------------------------------
function NewProjectForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const { mutate, isPending } = useCreateProject();

  const submit = () => {
    if (!name.trim()) return;
    mutate({ name: name.trim(), description: desc.trim() || undefined }, { onSuccess: onDone });
  };

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden px-3 pb-2"
    >
      <div className="border rounded-md p-3 space-y-2 bg-muted/30">
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Project name…"
          className="w-full text-xs bg-transparent border-b border-border pb-1 outline-none placeholder:text-muted-foreground"
        />
        <input
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          placeholder="Description (optional)"
          className="w-full text-xs bg-transparent outline-none placeholder:text-muted-foreground"
        />
        <div className="flex gap-2 pt-1">
          <button
            onClick={submit}
            disabled={isPending || !name.trim()}
            className="flex-1 text-xs bg-primary text-primary-foreground rounded px-2 py-1 disabled:opacity-50"
          >
            {isPending ? "Creating…" : "Create"}
          </button>
          <button onClick={onDone} className="text-xs text-muted-foreground hover:text-foreground px-2">
            Cancel
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Document row inside a project
// ---------------------------------------------------------------------------
function DocRow({ doc }: { doc: Document }) {
  const { scope, setDocument, clearDocument } = useScope();
  const { mutate: del } = useDeleteDocument();
  const isActive = scope.documentId === doc.id;

  const handleSelect = () => isActive ? clearDocument() : setDocument(doc.id, doc.original_filename);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Delete "${doc.original_filename}"?`)) {
      if (isActive) clearDocument();
      del(doc.id);
    }
  };

  return (
    <div
      onClick={handleSelect}
      className={`w-full text-left flex items-center gap-2 pl-6 pr-2 py-1.5 rounded-md transition-colors cursor-pointer group
        ${isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[doc.status] ?? "bg-gray-400"}`} />
      <div className="min-w-0 flex-1">
        <p className="text-xs truncate leading-snug">{doc.original_filename}</p>
        <p className="text-xs text-muted-foreground">
          {doc.status === "completed" ? `${doc.page_count}p` : doc.status}
        </p>
      </div>
      <button
        onClick={handleDelete}
        className="opacity-0 group-hover:opacity-100 text-xs px-1 py-0.5 rounded hover:bg-destructive/10 hover:text-destructive transition-opacity shrink-0"
        title="Delete document"
      >
        ✕
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project row
// ---------------------------------------------------------------------------
function ProjectRow({ project }: { project: Project }) {
  const { scope, setProject, clearProject } = useScope();
  const { mutate: del } = useDeleteProject();
  const isActive = scope.projectId === project.id;
  const [expanded, setExpanded] = useState(isActive);
  const [uploadOpen, setUploadOpen] = useState(false);
  const { data: docs = [] } = useDocuments(isActive || expanded ? project.id : undefined);

  const handleClick = () => {
    if (isActive) {
      clearProject();
      setExpanded(false);
    } else {
      setProject(project.id, project.name);
      setExpanded(true);
    }
  };

  return (
    <>
      <div className="space-y-0.5">
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors group
            ${isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"}`}
          onClick={handleClick}
        >
          <span className="text-xs shrink-0">{expanded ? "▾" : "▸"}</span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold truncate">{project.name}</p>
            <p className="text-xs text-muted-foreground">
              {project.document_count}d · {project.fact_count}f
            </p>
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={(e) => { e.stopPropagation(); setUploadOpen(true); }}
              className="text-xs px-1.5 py-0.5 rounded hover:bg-primary/10 hover:text-primary"
              title="Upload PDF to project"
            >
              +
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Delete "${project.name}"?`)) {
                  if (isActive) clearProject();
                  del(project.id);
                }
              }}
              className="text-xs px-1.5 py-0.5 rounded hover:bg-destructive/10 hover:text-destructive"
              title="Delete project"
            >
              ✕
            </button>
          </div>
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden space-y-0.5"
            >
              {docs.map((doc) => <DocRow key={doc.id} doc={doc} />)}
              {docs.length === 0 && (
                <p className="pl-6 text-xs text-muted-foreground py-1">No documents yet</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {uploadOpen && (
          <UploadSheet open={uploadOpen} onClose={() => setUploadOpen(false)} projectId={project.id} />
        )}
      </AnimatePresence>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
export function Sidebar() {
  const { data: projects = [] } = useProjects();
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const handler = () => setCreating(true);
    window.addEventListener("factforge:new-project", handler);
    return () => window.removeEventListener("factforge:new-project", handler);
  }, []);
  return (
    <aside className="fixed left-0 top-0 h-full w-[252px] border-r bg-background flex flex-col z-30">
      {/* Logo */}
      <div className="px-4 h-14 flex items-center border-b shrink-0">
        <Link href="/" className="flex items-center gap-2 font-semibold text-base">
          <span className="text-primary">⬡</span>
          <span>FactForge</span>
        </Link>
      </div>

      {/* Projects list */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
        <div className="flex items-center justify-between px-3 mb-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Projects</p>
          <button
            onClick={() => setCreating((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            title="New project"
          >
            + New
          </button>
        </div>

        <AnimatePresence>
          {creating && <NewProjectForm onDone={() => setCreating(false)} />}
        </AnimatePresence>

        {projects.length === 0 && !creating && (
          <p className="px-3 text-xs text-muted-foreground py-2">
            Create a project to get started
          </p>
        )}

        {projects.map((p) => <ProjectRow key={p.id} project={p} />)}
      </div>
    </aside>
  );
}
