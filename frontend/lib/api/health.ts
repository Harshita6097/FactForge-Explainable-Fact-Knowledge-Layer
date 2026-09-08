import apiClient from "./client";

export async function fetchHealth() {
  const { data } = await apiClient.get("/api/health");
  return data;
}
