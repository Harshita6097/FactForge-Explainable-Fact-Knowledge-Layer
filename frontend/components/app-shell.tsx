"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { TopBar } from "@/components/top-bar";
import { useAuth } from "@/contexts/AuthContext";

const PUBLIC_PATHS = ["/login", "/signup"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;
    const isPublic = PUBLIC_PATHS.includes(pathname);
    if (!user && !isPublic) router.replace("/login");
    if (user && isPublic) router.replace("/");
  }, [user, isLoading, pathname, router]);

  // Public pages render without shell
  if (PUBLIC_PATHS.includes(pathname)) return <>{children}</>;

  // Show nothing while checking auth
  if (isLoading || !user) return null;

  return (
    <div className="min-h-screen flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-h-screen pl-[252px]">
        <TopBar />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
