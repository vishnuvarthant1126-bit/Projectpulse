"use client";

import { ArrowUp, CircleAlert, FlaskConical, LoaderCircle, MessageSquareText, RotateCcw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AskResponse, Passage, RetrievalMode } from "@/lib/types";

import { AnswerView } from "./answer-view";

export interface ChatMessage {
  id: string;
  question: string;
  mode: RetrievalMode;
  status: "loading" | "done" | "error";
  response?: AskResponse;
  error?: string;
}

const MODES: { value: RetrievalMode; label: string; hint: string }[] = [
  { value: "hybrid", label: "Hybrid", hint: "Keyword and semantic results merged with reciprocal rank fusion" },
  { value: "keyword", label: "Keyword", hint: "BM25 keyword matching only" },
  { value: "semantic", label: "Semantic", hint: "Embedding similarity only" },
];

export function ChatPanel({
  messages,
  suggestions,
  suggestionsPrecomputed,
  readyCount,
  pendingCount,
  onAsk,
  onRetry,
  onOpenSource,
}: {
  messages: ChatMessage[];
  suggestions: string[];
  suggestionsPrecomputed: boolean;
  readyCount: number;
  pendingCount: number;
  onAsk: (q: string, mode: RetrievalMode) => void;
  onRetry: (m: ChatMessage) => void;
  onOpenSource: (p: Passage) => void;
}) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const inputId = useId();
  const endRef = useRef<HTMLDivElement>(null);
  const busy = messages.some((m) => m.status === "loading");
  const disabled = readyCount === 0;

  const lastStatus = messages.at(-1)?.status;
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, lastStatus]);

  function submit(q: string) {
    const text = q.trim();
    if (!text || busy || disabled) return;
    onAsk(text, mode);
    setQuestion("");
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-5 md:px-8" aria-live="polite" aria-busy={busy}>
        {messages.length === 0 && (
          <div className="mx-auto max-w-2xl space-y-4 pt-4">
            <div className="flex items-center gap-2 text-muted-foreground">
              <MessageSquareText className="size-5" aria-hidden />
              <p className="text-sm">
                {disabled
                  ? pendingCount > 0
                    ? "Documents are still processing or waiting for a confirmed date. Questions open once at least one is ready."
                    : "Upload documents to this project to start asking questions."
                  : "Ask about changes, delays, blockers or decisions. Every answer cites the passages it relies on."}
              </p>
            </div>
            {suggestions.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-medium">Suggested questions</h2>
                  {suggestionsPrecomputed && (
                    <Badge variant="warning">
                      <FlaskConical aria-hidden /> Precomputed demo answers
                    </Badge>
                  )}
                </div>
                <ul className="grid gap-2 sm:grid-cols-2">
                  {suggestions.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        disabled={disabled || busy}
                        onClick={() => submit(s)}
                        className="h-full w-full rounded-lg border bg-card p-3 text-left text-sm transition-colors hover:border-primary/40 hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {messages.map((m) => (
          <article key={m.id} className="mx-auto max-w-4xl space-y-3" aria-label={`Question: ${m.question}`}>
            <div className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
                {m.question}
              </p>
            </div>
            <div className="rounded-xl border bg-card p-4 shadow-sm md:p-5">
              {m.status === "loading" && (
                <div className="space-y-3" role="status">
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <LoaderCircle className="size-4 animate-spin" aria-hidden /> Searching documents and checking
                    evidence…
                  </p>
                  <Skeleton className="h-4 w-11/12" />
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-24 w-full" />
                </div>
              )}
              {m.status === "error" && (
                <Alert variant="destructive">
                  <CircleAlert aria-hidden />
                  <AlertTitle>Could not answer this question</AlertTitle>
                  <AlertDescription>
                    <p>{m.error}</p>
                    <Button variant="outline" size="sm" className="mt-2" onClick={() => onRetry(m)}>
                      <RotateCcw aria-hidden /> Try again
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
              {m.status === "done" && m.response && <AnswerView r={m.response} onOpen={onOpenSource} />}
            </div>
          </article>
        ))}
        <div ref={endRef} />
      </div>

      <form
        className="border-t bg-background/95 px-4 py-3 backdrop-blur md:px-8"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <div className="mx-auto max-w-4xl space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <ToggleGroup
              type="single"
              value={mode}
              onValueChange={(v) => v && setMode(v as RetrievalMode)}
              aria-label="Retrieval mode"
            >
              {MODES.map((m) => (
                <ToggleGroupItem key={m.value} value={m.value} title={m.hint} aria-label={`${m.label}: ${m.hint}`}>
                  {m.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            <span className="text-xs text-muted-foreground">
              {readyCount} document{readyCount === 1 ? "" : "s"} searchable
            </span>
          </div>
          <div className="flex items-end gap-2">
            <label htmlFor={inputId} className="sr-only">
              Ask a question about this project
            </label>
            <Textarea
              id={inputId}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit(question);
                }
              }}
              placeholder={
                disabled
                  ? "Waiting for a ready document…"
                  : "Ask what changed, what is delayed, or what needs attention"
              }
              className="max-h-40 min-h-11 resize-none bg-card"
              maxLength={1000}
              rows={1}
              disabled={disabled}
            />
            <Button
              type="submit"
              size="icon"
              className="size-11 shrink-0"
              disabled={!question.trim() || busy || disabled}
              aria-label="Ask"
            >
              {busy ? <LoaderCircle className="animate-spin" aria-hidden /> : <ArrowUp aria-hidden />}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
