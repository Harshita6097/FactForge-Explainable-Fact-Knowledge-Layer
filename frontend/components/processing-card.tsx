"use client";

import { motion } from "framer-motion";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useProcessingProgress } from "@/hooks/useProcessingProgress";

const STAGE_LABELS: Record<string, string> = {
  pending:    "Queued",
  processing: "Extracting pages…",
  extracted:  "Pages extracted",
  mining:     "Mining facts with AI…",
  analyzing:  "Detecting relationships…",
  completed:  "Complete",
  failed:     "Failed",
};

const STAGE_PCT: Record<string, number> = {
  pending:    0,
  processing: 10,
  extracted:  25,
  mining:     60,
  analyzing:  85,
  completed:  100,
  failed:     100,
};

interface Props {
  docId: string;
  filename: string;
}

export function ProcessingCard({ docId, filename }: Props) {
  const { progress } = useProcessingProgress(docId);

  const stage = progress?.stage || "pending";
  const pct = progress?.pct ?? STAGE_PCT[stage] ?? 0;
  const isComplete = stage === "completed";
  const isFailed = stage === "failed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="border rounded-lg p-4 space-y-3"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{filename}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {STAGE_LABELS[stage] || stage}
          </p>
        </div>
        <Badge
          variant={isComplete ? "default" : isFailed ? "destructive" : "secondary"}
          className={isComplete ? "bg-green-600 hover:bg-green-600" : ""}
        >
          {isComplete ? "Done" : isFailed ? "Failed" : "Processing"}
        </Badge>
      </div>

      <Progress
        value={pct}
        className={`h-1.5 ${isFailed ? "[&>div]:bg-destructive" : isComplete ? "[&>div]:bg-green-500" : ""}`}
      />

      {progress && (
        <div className="flex gap-4 text-xs text-muted-foreground">
          {progress.page_count > 0 && (
            <span>
              {progress.processed_pages}/{progress.page_count} pages
            </span>
          )}
          {progress.facts_found > 0 && (
            <span>{progress.facts_found} facts</span>
          )}
          {progress.relationships_found > 0 && (
            <span>{progress.relationships_found} relationships</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
