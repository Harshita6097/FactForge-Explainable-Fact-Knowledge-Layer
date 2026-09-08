import { useQuery } from "@tanstack/react-query";
import { fetchTimeline } from "@/lib/api/timeline";

export function useTimeline(params?: { entity?: string; attribute?: string }) {
  return useQuery({
    queryKey: ["timeline", params],
    queryFn: () => fetchTimeline(params),
    staleTime: 20_000,
  });
}
