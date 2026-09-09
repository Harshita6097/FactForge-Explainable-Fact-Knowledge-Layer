"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ProcessingCard } from "@/components/processing-card";
import { uploadDocument } from "@/lib/api/documents";
import { useQueryClient } from "@tanstack/react-query";

interface UploadItem {
  file: File;
  progress: number;
  status: "queued" | "uploading" | "done" | "error";
  error?: string;
  docId?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  projectId?: string;
}

export function UploadSheet({ open, onClose, projectId }: Props) {
  const qc = useQueryClient();
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
      const doc = await uploadDocument(file, projectId, (pct) => {
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
      qc.invalidateQueries({ queryKey: ["projects"] });
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
  }, [items.length]);

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
      />
      {/* Sheet */}
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 30, stiffness: 300 }}
        className="fixed right-0 top-0 z-50 h-full w-full max-w-md bg-background border-l shadow-xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <p className="font-semibold">Upload PDFs{projectId ? " to project" : ""}</p>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => document.getElementById("sheet-file-input")?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
              ${dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"}`}
          >
            <input
              id="sheet-file-input"
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
                  <span className="text-sm font-medium truncate max-w-[200px]">{item.file.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    item.status === "error"
                      ? "bg-red-100 text-red-700"
                      : "bg-blue-100 text-blue-700"
                  }`}>
                    {item.status === "uploading" ? `${item.progress}%` : item.status}
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
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Processing</p>
              {processingDocIds.map((d) => (
                <ProcessingCard key={d.id} docId={d.id} filename={d.name} />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t">
          <Button variant="outline" className="w-full" onClick={onClose}>Done</Button>
        </div>
      </motion.div>
    </>
  );
}
