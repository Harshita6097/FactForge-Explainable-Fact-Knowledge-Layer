import apiClient from "./client";
import { Project } from "@/types";

export async function fetchProjects(): Promise<Project[]> {
  const { data } = await apiClient.get("/api/projects");
  return data;
}

export async function fetchProject(id: string): Promise<Project> {
  const { data } = await apiClient.get(`/api/projects/${id}`);
  return data;
}

export async function createProject(name: string, description?: string): Promise<Project> {
  const { data } = await apiClient.post("/api/projects", { name, description });
  return data;
}

export async function updateProject(id: string, name: string, description?: string): Promise<Project> {
  const { data } = await apiClient.patch(`/api/projects/${id}`, { name, description });
  return data;
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`/api/projects/${id}`);
}

export async function fetchProjectStats(id: string) {
  const { data } = await apiClient.get(`/api/projects/${id}/stats`);
  return data;
}
