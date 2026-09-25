"use client";

import {
  CircleAlert,
  CircleCheck,
  CircleHelp,
  FlaskConical,
  Info,
  Lightbulb,
  Scale,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate } from "@/lib/format";
import type { AskResponse, Blocker } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Citations, CitedText, type OpenSource } from "./citation";
import { EvidencePanel } from "./evidence-panel";

const NOT_STATED = "Not stated";
const MODE_LABELS = { hybrid: "Hybrid", keyword: "Keyword", semantic: "Semantic" } as const;

function Muted({ value }: { value: string }) {
  return <span className={cn(value === NOT_STATED && "text-muted-foreground italic")}>{value}</span>;
}

function ModeBadge({ r }: { r: AskResponse }) {
  switch (r.answer_mode) {
    case "live":
      return (
        <Badge variant="info">
          <Sparkles aria-hidden /> Live AI answer{r.model ? ` · ${r.model}` : ""}
        </Badge>
      );
    case "precomputed_demo":
      return (
        <Badge variant="warning">
          <FlaskConical aria-hidden /> Precomputed demo answer (not live AI)
        </Badge>
      );
    case "retrieval_only":
      return <Badge variant="secondary">Evidence only (no answer generated)</Badge>;
    default:
      return <Badge variant="secondary">No matching evidence</Badge>;
  }
}

const BLOCKER_STATUS: Record<Blocker["status"], { label: string; className: string; Icon: typeof CircleAlert }> = {
  unresolved_in_latest: {
    label: "Unresolved in latest update",
    className: "bg-destructive/10 text-destructive border-destructive/30",
    Icon: CircleAlert,
  },
  resolved: {
    label: "Resolved",
    className: "bg-success-muted text-success-foreground border-transparent",
    Icon: CircleCheck,
  },
  status_unknown: {
    label: "Status not confirmed",
    className: "bg-muted text-muted-foreground border-transparent",
    Icon: CircleHelp,
  },
};

function Section({
  title,
  icon,
  children,
  note,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  note?: string;
}) {
  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-1.5 text-sm font-semibold">
        {icon}
        {title}
      </h4>
      {note && <p className="-mt-1 text-xs text-muted-foreground">{note}</p>}
      {children}
    </section>
  );
}

export function AnswerView({ r, onOpen }: { r: AskResponse; onOpen: OpenSource }) {
  const a = r.answer;
  const v = r.validation;
  const passages = r.passages;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <ModeBadge r={r} />
        <Badge variant="outline">{MODE_LABELS[r.mode]} retrieval</Badge>
        {r.intents.includes("change") && <Badge variant="outline">Plan vs progress</Badge>}
        <span className="text-xs text-muted-foreground tabular-nums">{r.latency_ms} ms</span>
      </div>

      {r.notice && (
        <Alert variant={r.answer_mode === "precomputed_demo" ? "info" : "warning"}>
          <Info aria-hidden />
          <AlertDescription>{r.notice}</AlertDescription>
        </Alert>
      )}

      {a && a.answer_type === "insufficient_evidence" && (
        <Alert variant="warning">
          <TriangleAlert aria-hidden />
          <AlertTitle>Not enough evidence in this project&apos;s documents</AlertTitle>
          <AlertDescription>
            <p>
              <CitedText text={a.summary} passages={passages} onOpen={onOpen} />
            </p>
          </AlertDescription>
        </Alert>
      )}

      {a && a.answer_type === "answer" && a.summary && (
        <p className="text-[15px] leading-relaxed">
          <CitedText text={a.summary} passages={passages} onOpen={onOpen} />
        </p>
      )}

      {a && a.comparison.length > 0 && (
        <Section title="Plan versus latest reported status" icon={<Scale className="size-4" aria-hidden />}>
          {/* Table on wider screens */}
          <div className="hidden rounded-lg border md:block">
            <Table>
              <caption className="sr-only">
                Milestones: original commitment compared with latest reported status
              </caption>
              <TableHeader>
                <TableRow className="bg-muted/40">
                  <TableHead scope="col">Milestone</TableHead>
                  <TableHead scope="col">Original commitment</TableHead>
                  <TableHead scope="col">Latest reported</TableHead>
                  <TableHead scope="col">Documented reason</TableHead>
                  <TableHead scope="col">Owner</TableHead>
                  <TableHead scope="col">Sources</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {a.comparison.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{row.milestone}</TableCell>
                    <TableCell>
                      <Muted value={row.original_commitment} />
                    </TableCell>
                    <TableCell>
                      <Muted value={row.latest_status} />
                    </TableCell>
                    <TableCell className="max-w-64 whitespace-normal">
                      <Muted value={row.reason_for_change} />
                    </TableCell>
                    <TableCell>
                      <Muted value={row.owner} />
                    </TableCell>
                    <TableCell>
                      <Citations ids={row.citations} passages={passages} onOpen={onOpen} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {/* Stacked cards on small screens */}
          <ul className="space-y-2 md:hidden">
            {a.comparison.map((row, i) => (
              <li key={i} className="rounded-lg border p-3 text-sm">
                <p className="font-medium">{row.milestone}</p>
                <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  <dt className="text-muted-foreground">Planned</dt>
                  <dd>
                    <Muted value={row.original_commitment} />
                  </dd>
                  <dt className="text-muted-foreground">Latest</dt>
                  <dd>
                    <Muted value={row.latest_status} />
                  </dd>
                  <dt className="text-muted-foreground">Reason</dt>
                  <dd>
                    <Muted value={row.reason_for_change} />
                  </dd>
                  <dt className="text-muted-foreground">Owner</dt>
                  <dd>
                    <Muted value={row.owner} />
                  </dd>
                </dl>
                <div className="mt-2">
                  <Citations ids={row.citations} passages={passages} onOpen={onOpen} />
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {a && a.findings.length > 0 && (
        <Section title="Documented facts" icon={<ShieldCheck className="size-4" aria-hidden />}>
          <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed marker:text-muted-foreground">
            {a.findings.map((f, i) => (
              <li key={i}>
                {f.statement} <Citations ids={f.citations} passages={passages} onOpen={onOpen} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {a && a.conflicts.length > 0 && (
        <Section
          title="Sources disagree"
          icon={<TriangleAlert className="size-4 text-warning-foreground" aria-hidden />}
        >
          {a.conflicts.map((c, i) => (
            <div key={i} className="rounded-lg border border-warning/40 bg-warning-muted/60 p-3 text-sm">
              <p className="font-medium">{c.topic}</p>
              <ul className="mt-2 space-y-1.5">
                {c.positions.map((p, j) => (
                  <li key={j} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                    <span className="shrink-0 text-xs font-semibold tabular-nums text-warning-foreground sm:w-24 sm:pt-0.5">
                      {formatDate(p.source_date)}
                    </span>
                    <span>
                      {p.claim} <Citations ids={p.citations} passages={passages} onOpen={onOpen} />
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </Section>
      )}

      {a && a.blockers.length > 0 && (
        <Section title="Blockers" icon={<CircleAlert className="size-4" aria-hidden />}>
          <ul className="space-y-2">
            {a.blockers.map((b, i) => {
              const s = BLOCKER_STATUS[b.status];
              return (
                <li key={i} className="rounded-lg border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{b.blocker}</span>
                    <Badge className={s.className}>
                      <s.Icon aria-hidden /> {s.label}
                    </Badge>
                  </div>
                  {b.detail && (
                    <p className="mt-1 leading-relaxed text-muted-foreground">
                      {b.detail} <Citations ids={b.citations} passages={passages} onOpen={onOpen} />
                    </p>
                  )}
                  {!b.detail && <Citations ids={b.citations} passages={passages} onOpen={onOpen} />}
                </li>
              );
            })}
          </ul>
        </Section>
      )}

      {a && a.suggested_actions.length > 0 && (
        <Section
          title="Suggested actions"
          icon={<Lightbulb className="size-4" aria-hidden />}
          note="Recommendations based on the evidence. These are suggestions, not facts from the documents."
        >
          <ul className="space-y-2 rounded-lg border border-dashed p-3 text-sm">
            {a.suggested_actions.map((s, i) => (
              <li key={i}>
                <span className="font-medium">{s.action}</span>
                {s.rationale && <span className="text-muted-foreground"> {s.rationale}</span>}{" "}
                <Citations ids={s.citations} passages={passages} onOpen={onOpen} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {a && a.missing_information.length > 0 && (
        <Section title="Not found in the documents" icon={<CircleHelp className="size-4" aria-hidden />}>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {a.missing_information.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </Section>
      )}

      {!v.passed && (
        <Alert variant="warning">
          <TriangleAlert aria-hidden />
          <AlertTitle>Citation check found problems</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {v.invalid_citations.length > 0 && (
                <li>Removed citations to passages that were not retrieved: {v.invalid_citations.join(", ")}</li>
              )}
              {v.removed_items.map((x, i) => (
                <li key={`r${i}`}>Removed unsupported statement: {x}</li>
              ))}
              {v.unverified_dates.map((x, i) => (
                <li key={`d${i}`}>Date not found in the cited passages: {x}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <EvidencePanel
        passages={passages}
        mode={r.mode}
        onOpen={onOpen}
        defaultOpen={r.answer_mode === "retrieval_only"}
      />
    </div>
  );
}
