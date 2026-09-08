import apiClient from "./client";
import { Document } from "@/types";

export async function uploadDocument(file: File, onProgress?: (pct: number) => void): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post("/api/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

export async function fetchDocuments(): Promise<Document[]> {
  const { data } = await apiClient.get("/api/documents");
  return data;
}

export async function fetchDocument(id: string): Promise<Document> {
  const { data } = await apiClient.get(`/api/documents/${id}`);
  return data;
}

export async function fetchDocumentStatus(id: string) {
  const { data } = await apiClient.get(`/api/documents/${id}/status`);
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await apiClient.delete(`/api/documents/${id}`);
}
