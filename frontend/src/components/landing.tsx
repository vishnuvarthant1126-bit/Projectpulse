"use client";

import { CodeXml, FlaskConical, Plus, Scale, ShieldCheck, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { REPO_URL } from "@/lib/site";

const FEATURES = [
  {
    Icon: ShieldCheck,
    title: "Evidence-backed answers",
    body: "Every claim cites a passage you can open and read in context. Citations are checked by the server.",
  },
  {
    Icon: Scale,
    title: "Plan versus progress",
    body: "See each milestone's original commitment next to its latest reported status, reason and owner.",
  },
  {
    Icon: TriangleAlert,
    title: "Conflicts and open blockers",
    body: "Disagreeing sources are shown side by side with their dates. Unresolved blockers are kept apart from historical ones.",
  },
];

export function Landing({
  onTrySample,
  onCreate,
  sampleBusy,
  demoMode,
  readOnly = false,
}: {
  onTrySample: () => void;
  onCreate: () => void;
  sampleBusy: boolean;
  demoMode: boolean;
  readOnly?: boolean;
}) {
  return (
    <div className="flex flex-1 items-center justify-center overflow-y-auto px-4 py-10 md:px-8">
      <div className="max-w-3xl space-y-8 text-center">
        <div className="space-y-4">
          <p className="text-sm font-medium text-primary">ProjectPulse: ask your project what changed</p>
          <h1 className="text-3xl font-semibold tracking-tight text-balance md:text-5xl">
            Understand what changed. See what needs attention.
          </h1>
          <p className="mx-auto max-w-xl text-base text-pretty text-muted-foreground md:text-lg">
            Upload project plans, progress updates and meeting notes, then ask plain-language questions. Answers come
            only from your documents, with citations you can check.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" onClick={onTrySample} disabled={sampleBusy}>
            <FlaskConical aria-hidden /> {sampleBusy ? "Loading sample project…" : "Try sample project"}
          </Button>
          {readOnly ? (
            <Button size="lg" variant="outline" asChild>
              <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
                <CodeXml aria-hidden /> View source on GitHub
              </a>
            </Button>
          ) : (
            <Button size="lg" variant="outline" onClick={onCreate}>
              <Plus aria-hidden /> Create your own project
            </Button>
          )}
        </div>
        {demoMode && (
          <p className="text-xs text-muted-foreground">
            Demo mode: no answer model is configured. The sample project&apos;s suggested questions return clearly
            labelled precomputed answers, and other questions return the retrieved evidence only.
          </p>
        )}
        <ul className="grid gap-4 text-left sm:grid-cols-3">
          {FEATURES.map(({ Icon, title, body }) => (
            <li key={title} className="rounded-xl border bg-card p-4">
              <Icon className="size-5 text-primary" aria-hidden />
              <h2 className="mt-2 text-sm font-semibold">{title}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
