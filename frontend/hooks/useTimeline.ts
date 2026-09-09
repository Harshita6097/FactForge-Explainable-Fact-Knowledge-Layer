import { useQuery } from "@tanstack/react-query";
import { fetchTimeline } from "@/lib/api/timeline";

export function useTimeline(params?: {
  entity?: string;
  attribute?: string;
  project_id?: string;
  document_id?: string;
}) {
  return useQuery({
    queryKey: ["timeline", params],
    queryFn: () => fetchTimeline(params),
    staleTime: 20_000,
  });
}
