"use client";

import type { Passage } from "@/lib/types";
import { cn } from "@/lib/utils";

export type OpenSource = (passage: Passage) => void;

export function CitationChip({ id, passages, onOpen }: { id: string; passages: Passage[]; onOpen: OpenSource }) {
  const p = passages.find((x) => x.source_id === id);
  if (!p) return null;
  const where = `${p.document_name}${p.page ? `, page ${p.page}` : ""}`;
  return (
    <button
      type="button"
      onClick={() => onOpen(p)}
      title={where}
      aria-label={`Source ${id}: ${where}. Open passage`}
      className={cn(
        "mx-0.5 inline-flex h-5 min-w-7 items-center justify-center rounded-md border border-primary/25 bg-accent px-1.5 align-baseline",
        "text-[11px] font-semibold text-accent-foreground tabular-nums transition-colors",
        "hover:bg-primary hover:text-primary-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
      )}
    >
      {id}
    </button>
  );
}

export function Citations({ ids, passages, onOpen }: { ids: string[]; passages: Passage[]; onOpen: OpenSource }) {
  if (!ids.length) return null;
  return (
    <span className="whitespace-nowrap">
      {ids.map((id) => (
        <CitationChip key={id} id={id} passages={passages} onOpen={onOpen} />
      ))}
    </span>
  );
}

/** Renders text containing inline markers like "[S1]" or "[S1, S3]" as clickable chips. */
export function CitedText({ text, passages, onOpen }: { text: string; passages: Passage[]; onOpen: OpenSource }) {
  const parts = text.split(/(\[(?:S\d+\s*,?\s*)+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[((?:S\d+\s*,?\s*)+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const ids = m[1].split(/[\s,]+/).filter(Boolean);
        return <Citations key={i} ids={ids} passages={passages} onOpen={onOpen} />;
      })}
    </>
  );
}
