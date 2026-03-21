import type { Urgency } from "@/types/api";

export function ndviColor(score: number): string {
  if (score < 40) return "#ef4444";
  if (score < 65) return "#f59e0b";
  if (score < 80) return "#84cc16";
  return "#16a34a";
}

export const URGENCY_COLOR: Record<Urgency, string> = {
  low: "#6b7280",
  medium: "#3b82f6",
  high: "#f97316",
  critical: "#ef4444",
};
