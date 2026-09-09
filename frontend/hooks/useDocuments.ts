import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchDocuments, fetchDocument, fetchDocumentStatus, deleteDocument } from "@/lib/api/documents";

export function useDocuments(projectId?: string) {
  return useQuery({
    queryKey: ["documents", { projectId }],
    queryFn: () => fetchDocuments(projectId),
  });
}

export function useDocument(id: string) {
  return useQuery({ queryKey: ["documents", id], queryFn: () => fetchDocument(id), enabled: !!id });
}

export function useDocumentStatus(id: string, enabled = true) {
  return useQuery({
    queryKey: ["documents", id, "status"],
    queryFn: () => fetchDocumentStatus(id),
    enabled: !!id && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 2000;
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
