"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Navbar } from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { uploadDocument } from "@/lib/api/documents";
import { useDocuments, useDeleteDocument } from "@/hooks/useDocuments";
import { Document } from "@/types";
import { useQueryClient } from "@tanstack/react-query";

interface UploadItem {
  file: File;
  progress: number;
  status: "queued" | "uploading" | "done" | "error";
  error?: string;
  docId?: string;
}

const statusColor: Record<Document["status"], string> = {
  pending: "secondary",
  processing: "secondary",
  extracted: "secondary",
  completed: "default",
  failed: "destructive",
} as any;

export default function UploadPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: documents = [] } = useDocuments();
  const { mutate: deleteDoc } = useDeleteDocument();
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);

  const addFiles = (files: FileList | File[]) => {
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) return;
    setItems((prev) => [
      ...prev,
      ...pdfs.map((f) => ({ file: f, progress: 0, status: "queued" as const })),
    ]);
    const offset = items.length;
    pdfs.forEach((f, i) => startUpload(f, offset + i));
  };

  const startUpload = async (file: File, index: number) => {
    setItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, status: "uploading" } : it))
    );
    try {
      const doc = await uploadDocument(file, (pct) => {
        setItems((prev) =>
          prev.map((it, i) => (i === index ? { ...it, progress: pct } : it))
        );
      });
      setItems((prev) =>
        prev.map((it, i) =>
          i === index ? { ...it, status: "done", progress: 100, docId: doc.id } : it
        )
      );
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

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-4xl mx-auto px-4 py-10 w-full space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Upload PDFs</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Drop one or multiple PDFs. Each will be processed automatically.
          </p>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer
            ${dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}`}
          onClick={() => document.getElementById("file-input")?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          <div className="text-4xl mb-3">📄</div>
          <p className="font-medium">Drag & drop PDFs here</p>
          <p className="text-sm text-muted-foreground mt-1">or click to browse</p>
        </div>

        {/* Upload queue */}
        <AnimatePresence>
          {items.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="border rounded-lg p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium truncate max-w-xs">{item.file.name}</span>
                <Badge variant={item.status === "error" ? "destructive" : item.status === "done" ? "default" : "secondary"}>
                  {item.status}
                </Badge>
              </div>
              {item.status === "uploading" && <Progress value={item.progress} className="h-1.5" />}
              {item.status === "error" && (
                <p className="text-xs text-destructive">{item.error}</p>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Existing documents */}
        {documents.length > 0 && (
          <div className="space-y-3">
            <h2 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
              Uploaded Documents
            </h2>
            {documents.map((doc) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="border rounded-lg p-4 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">{doc.original_filename}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {doc.page_count} pages · {new Date(doc.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant={(statusColor[doc.status] as any) ?? "secondary"}>
                    {doc.status}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => deleteDoc(doc.id)}
                  >
                    Delete
                  </Button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
