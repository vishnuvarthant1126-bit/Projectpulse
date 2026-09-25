"use client";

import { useEffect, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { DOC_TYPE_LABELS, type DocumentContent, type Passage } from "@/lib/types";

export function SourceViewer({ passage, onClose }: { passage: Passage | null; onClose: () => void }) {
  // Results are keyed by document id so a stale document is never shown for a new citation.
  const [loaded, setLoaded] = useState<{ docId: string; content?: DocumentContent; error?: string } | null>(null);
  const markRef = useRef<HTMLElement | null>(null);
  const docId = passage?.document_id;
  const current = loaded && loaded.docId === docId ? loaded : null;
  const content = current?.content ?? null;
  const error = current?.error ?? null;

  useEffect(() => {
    if (!docId) return;
    let cancelled = false;
    api
      .documentContent(docId)
      .then((c) => !cancelled && setLoaded({ docId, content: c }))
      .catch((e: Error) => !cancelled && setLoaded({ docId, error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [docId]);

  useEffect(() => {
    if (content && markRef.current) {
      markRef.current.scrollIntoView({ block: "center" });
    }
  }, [content, passage?.chunk_id]);

  return (
    <Sheet open={!!passage} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="gap-0">
        <SheetHeader className="border-b">
          <SheetTitle className="break-all">{passage?.document_name ?? "Source"}</SheetTitle>
          <SheetDescription asChild>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {passage && (
                <>
                  <span className="rounded bg-accent px-1.5 py-0.5 font-semibold text-accent-foreground">
                    {passage.source_id}
                  </span>
                  <Badge variant="outline">{DOC_TYPE_LABELS[passage.doc_type]}</Badge>
                  <span>Reporting date {formatDate(passage.reporting_date)}</span>
                  {passage.page != null && <span>· Page {passage.page}</span>}
                </>
              )}
            </div>
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-4" tabIndex={0} aria-label="Document text">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {!content && !error && (
            <div className="space-y-3" aria-busy="true" aria-label="Loading document">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-4 w-1/4" />
              <Skeleton className="h-28 w-full" />
            </div>
          )}
          {content && passage && (
            <article className="space-y-5 text-sm leading-relaxed">
              {content.sections.map((s, i) => {
                const prev = content.sections[i - 1];
                const showPage = s.page != null && s.page !== prev?.page;
                const isTarget = s.id === passage.section_id;
                const showHeading = s.heading && (s.heading !== prev?.heading || showPage);
                return (
                  <section key={s.id} className="space-y-1.5">
                    {showPage && (
                      <p className="border-b pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                        Page {s.page}
                      </p>
                    )}
                    {showHeading && <h3 className="font-semibold">{s.heading}</h3>}
                    <p className="whitespace-pre-wrap">
                      {isTarget ? (
                        <>
                          {s.text.slice(0, passage.char_start)}
                          <mark
                            ref={markRef}
                            className="rounded-sm bg-highlight px-0.5 text-foreground ring-2 ring-highlight"
                            aria-label={`Cited passage ${passage.source_id}`}
                          >
                            {s.text.slice(passage.char_start, passage.char_end)}
                          </mark>
                          {s.text.slice(passage.char_end)}
                        </>
                      ) : (
                        s.text
                      )}
                    </p>
                  </section>
                );
              })}
            </article>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
