"use client";

import { ChevronDown, FileText } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { formatDate } from "@/lib/format";
import { DOC_TYPE_LABELS, type Passage, type RetrievalMode } from "@/lib/types";
import { cn } from "@/lib/utils";

import type { OpenSource } from "./citation";

function RankLine({ p, mode }: { p: Passage; mode: RetrievalMode }) {
  const bits: string[] = [];
  if (p.fused_rank != null) bits.push(`${mode === "hybrid" ? "Fused" : "Retrieval"} rank ${p.fused_rank}`);
  if (p.rrf_score != null) bits.push(`RRF ${p.rrf_score.toFixed(4)}`);
  if (p.keyword_rank != null) bits.push(`keyword #${p.keyword_rank}`);
  if (p.semantic_rank != null) bits.push(`semantic #${p.semantic_rank}`);
  if (!bits.length) bits.push("Not in the ranked list");
  return <span className="tabular-nums">{bits.join(" · ")}</span>;
}

export function EvidencePanel({
  passages,
  mode,
  onOpen,
  defaultOpen = false,
}: {
  passages: Passage[];
  mode: RetrievalMode;
  onOpen: OpenSource;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!passages.length) return null;
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border bg-muted/30">
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left text-sm font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <span>
            Evidence: {passages.length} retrieved passage{passages.length === 1 ? "" : "s"}
            <span className="ml-2 font-normal text-muted-foreground">({mode} retrieval)</span>
          </span>
          <ChevronDown className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ol className="space-y-2 px-3 pb-3" aria-label="Retrieved passages">
          {passages.map((p) => (
            <li key={p.chunk_id} className="rounded-md border bg-card p-3">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                <span className="rounded bg-accent px-1.5 py-0.5 font-semibold text-accent-foreground">
                  {p.source_id}
                </span>
                <span className="font-medium break-all">{p.document_name}</span>
                <Badge variant="outline">{DOC_TYPE_LABELS[p.doc_type]}</Badge>
                <span className="text-muted-foreground">{formatDate(p.reporting_date)}</span>
                {p.page != null && <span className="text-muted-foreground">Page {p.page}</span>}
              </div>
              {p.heading && <p className="mt-1 text-xs font-medium text-muted-foreground">{p.heading}</p>}
              <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed">{p.text}</p>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  <RankLine p={p} mode={mode} />
                  {p.included_for && <span className="ml-1 italic">· {p.included_for}</span>}
                </span>
                <Button variant="ghost" size="sm" className="h-7" onClick={() => onOpen(p)}>
                  <FileText aria-hidden /> View in document
                </Button>
              </div>
            </li>
          ))}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  );
}
