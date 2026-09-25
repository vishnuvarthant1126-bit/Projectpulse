import type { DocStatus } from "./types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-03-06" -> "6 Mar 2026". Parsed manually so time zones can never shift the day. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "No date";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const STATUS_LABELS: Record<DocStatus, string> = {
  uploaded: "Queued",
  extracting: "Extracting text",
  needs_review: "Confirm date",
  indexing: "Indexing",
  ready: "Ready",
  failed: "Failed",
};

export const isProcessing = (s: DocStatus) => s === "uploaded" || s === "extracting" || s === "indexing";
