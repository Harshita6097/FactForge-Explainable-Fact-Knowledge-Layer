import apiClient from "./client";
import { User } from "@/types";

export interface AuthResponse {
  token: string;
  user: User;
}

export async function register(name: string, email: string, password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post("/api/auth/register", { name, email, password });
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post("/api/auth/login", { email, password });
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await apiClient.get("/api/auth/me");
  return data;
}
