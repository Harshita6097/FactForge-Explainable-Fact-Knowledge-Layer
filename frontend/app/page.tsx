"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api/health";
import { Navbar } from "@/components/navbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function HomePage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
  });

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto px-4 py-12 w-full">
        <div className="mb-10">
          <h1 className="text-3xl font-bold tracking-tight">FactForge</h1>
          <p className="text-muted-foreground mt-1">
            Explainable Fact Knowledge Layer — upload PDFs, explore structured facts.
          </p>
        </div>

        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">API Status</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-3">
            {isLoading && <Badge variant="secondary">Checking…</Badge>}
            {isError && <Badge variant="destructive">Offline</Badge>}
            {data && (
              <>
                <Badge variant="default" className="bg-green-600 hover:bg-green-600">
                  Online
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {data.service} v{data.version}
                </span>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
