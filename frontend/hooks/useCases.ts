import { useQuery } from "@tanstack/react-query";
import { fetchCases, CasesResponse } from "@/lib/api/cases";

export function useCases(projectId?: string) {
  return useQuery<CasesResponse>({
    queryKey: ["cases", projectId],
    queryFn: () => fetchCases(projectId),
  });
}
