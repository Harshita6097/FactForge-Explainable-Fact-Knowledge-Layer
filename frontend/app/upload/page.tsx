"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ProcessingCard } from "@/components/processing-card";
import { uploadDocument } from "@/lib/api/documents";
import { useDocuments, useDeleteDocument } from "@/hooks/useDocuments";
import { useQueryClient } from "@tanstack/react-query";
import { Document } from "@/types";

interface UploadItem {
  file: File;
  progress: number;
  status: "queued" | "uploading" | "done" | "error";
  error?: string;
  docId?: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:    { label: "Pending",    color: "bg-gray-100 text-gray-600" },
  processing: { label: "Processing", color: "bg-blue-100 text-blue-700" },
  extracted:  { label: "Extracting", color: "bg-blue-100 text-blue-700" },
  mining:     { label: "Mining facts", color: "bg-violet-100 text-violet-700" },
  analyzing:  { label: "Analyzing",  color: "bg-amber-100 text-amber-700" },
  completed:  { label: "Ready",      color: "bg-green-100 text-green-700" },
  failed:     { label: "Failed",     color: "bg-red-100 text-red-700" },
};

function DocumentCard({ doc }: { doc: Document }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { mutate: deleteDoc, isPending } = useDeleteDocument();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const cfg = STATUS_CONFIG[doc.status] ?? STATUS_CONFIG.pending;
  const isReady = doc.status === "completed";

  const handleDelete = () => {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    deleteDoc(doc.id, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["facts"] });
        qc.invalidateQueries({ queryKey: ["relationships"] });
        qc.invalidateQueries({ queryKey: ["stats"] });
        setConfirmDelete(false);
      },
    });
  };

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className={`transition-all ${isReady ? "hover:shadow-md hover:border-primary/40" : ""}`}>
        <CardContent className="p-5">
          <div className="flex items-start justify-between gap-4">
            {/* Left: doc info */}
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-lg">📄</span>
                <span className="font-semibold text-sm truncate max-w-xs">
                  {doc.original_filename}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.color}`}>
                  {cfg.label}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {doc.page_count} pages · Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
              </p>

              {/* Action buttons — only when ready */}
              {isReady && (
                <div className="flex gap-2 flex-wrap pt-1">
                  <button
                    onClick={() => router.push(`/facts?doc=${doc.id}`)}
                    className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-medium"
                  >
                    View Facts
                  </button>
                  <button
                    onClick={() => router.push(`/relationships?doc=${doc.id}`)}
                    className="text-xs px-3 py-1.5 rounded-md border hover:bg-muted transition-colors font-medium"
                  >
                    Relationships
                  </button>
                  <button
                    onClick={() => router.push(`/timeline?doc=${doc.id}`)}
                    className="text-xs px-3 py-1.5 rounded-md border hover:bg-muted transition-colors font-medium"
                  >
                    Timeline
                  </button>
                </div>
              )}
            </div>

            {/* Right: delete */}
            <div className="shrink-0 flex flex-col items-end gap-2">
              {confirmDelete ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-destructive font-medium">Sure?</span>
                  <button
                    onClick={handleDelete}
                    disabled={isPending}
                    className="text-xs px-2 py-1 rounded bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
                  >
                    {isPending ? "…" : "Yes, delete"}
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="text-xs px-2 py-1 rounded border hover:bg-muted transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleDelete}
                  className="text-xs text-muted-foreground hover:text-destructive transition-colors"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function UploadPage() {
  const qc = useQueryClient();
  const { data: documents = [], isLoading } = useDocuments();
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [processingDocIds, setProcessingDocIds] = useState<{ id: string; name: string }[]>([]);

  const addFiles = (files: FileList | File[]) => {
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) return;
    const offset = items.length;
    setItems((prev) => [
      ...prev,
      ...pdfs.map((f) => ({ file: f, progress: 0, status: "queued" as const })),
    ]);
    pdfs.forEach((f, i) => startUpload(f, offset + i));
  };

  const startUpload = async (file: File, index: number) => {
    setItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, status: "uploading" } : it))
    );
    try {
      const doc = await uploadDocument(file, undefined, (pct: number) => {
        setItems((prev) =>
          prev.map((it, i) => (i === index ? { ...it, progress: pct } : it))
        );
      });
      setItems((prev) =>
        prev.map((it, i) =>
          i === index ? { ...it, status: "done", progress: 100, docId: doc.id } : it
        )
      );
      setProcessingDocIds((prev) => [...prev, { id: doc.id, name: file.name }]);
      qc.invalidateQueries({ queryKey: ["documents"] });
    } catch (e: any) {
      setItems((prev) =>
        prev.map((it, i) =>
          i === index ? { ...it, status: "error", error: e.message } : it
        )
      );
    }
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  }, []);

  const processingIds = new Set(processingDocIds.map((p) => p.id));
  const listedDocs = documents.filter((d) => !processingIds.has(d.id));

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-3xl mx-auto px-4 py-10 w-full space-y-8">

        <div>
          <h1 className="text-2xl font-bold">Documents</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload PDFs — facts, relationships, and timeline are extracted automatically.
          </p>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => document.getElementById("file-input")?.click()}
          className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer
            ${dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"}`}
        >
          <input
            id="file-input"
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          <div className="text-3xl mb-2">📄</div>
          <p className="font-medium text-sm">Drag & drop PDFs here</p>
          <p className="text-xs text-muted-foreground mt-1">or click to browse · multiple files supported</p>
        </div>

        {/* Upload progress */}
        <AnimatePresence>
          {items.filter((it) => it.status !== "done").map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="border rounded-lg p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium truncate max-w-xs">{item.file.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  item.status === "error"
                    ? "bg-red-100 text-red-700"
                    : "bg-blue-100 text-blue-700"
                }`}>
                  {item.status === "uploading" ? `Uploading ${item.progress}%` : item.status}
                </span>
              </div>
              {item.status === "uploading" && <Progress value={item.progress} className="h-1" />}
              {item.status === "error" && (
                <p className="text-xs text-destructive">{item.error}</p>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Live processing (SSE) */}
        {processingDocIds.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Processing
            </p>
            {processingDocIds.map((d) => (
              <ProcessingCard key={d.id} docId={d.id} filename={d.name} />
            ))}
          </div>
        )}

        {/* Document list */}
        {!isLoading && listedDocs.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {listedDocs.length} Document{listedDocs.length !== 1 ? "s" : ""}
            </p>
            {listedDocs.map((doc) => (
              <DocumentCard key={doc.id} doc={doc} />
            ))}
          </div>
        )}

        {!isLoading && documents.length === 0 && processingDocIds.length === 0 && (
          <div className="text-center py-16 text-muted-foreground">
            <p className="text-3xl mb-3">📭</p>
            <p className="font-medium text-sm">No documents yet</p>
            <p className="text-xs mt-1">Upload a PDF above to get started</p>
          </div>
        )}
      </main>
    </div>
  );
}
