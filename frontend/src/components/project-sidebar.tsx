"use client";

import {
  CalendarDays,
  CircleAlert,
  CircleCheck,
  FileText,
  FlaskConical,
  LoaderCircle,
  Pencil,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { useId, useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, isProcessing, STATUS_LABELS } from "@/lib/format";
import { DOC_TYPE_LABELS, type Project, type ProjectDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

function StatusBadge({ doc }: { doc: ProjectDocument }) {
  if (doc.status === "ready")
    return (
      <Badge variant="success">
        <CircleCheck aria-hidden /> Ready
      </Badge>
    );
  if (doc.status === "failed")
    return (
      <Badge variant="destructive">
        <CircleAlert aria-hidden /> Failed
      </Badge>
    );
  if (doc.status === "needs_review")
    return (
      <Badge variant="warning">
        <CalendarDays aria-hidden /> Confirm date
      </Badge>
    );
  return (
    <Badge variant="info">
      <LoaderCircle className="animate-spin" aria-hidden /> {STATUS_LABELS[doc.status]}
    </Badge>
  );
}

function DocumentItem({
  doc,
  onEdit,
  onDelete,
  readOnly,
}: {
  readOnly: boolean;
  doc: ProjectDocument;
  onEdit: (d: ProjectDocument) => void;
  onDelete: (d: ProjectDocument) => void;
}) {
  return (
    <li className="group rounded-lg border bg-card p-2.5">
      <div className="flex items-start gap-2">
        <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={doc.filename}>
            {doc.filename}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {DOC_TYPE_LABELS[doc.doc_type]} ·{" "}
            {doc.reporting_date ? formatDate(doc.reporting_date) : "Date not confirmed"}
            {doc.page_count ? ` · ${doc.page_count} pp` : ""}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <StatusBadge doc={doc} />
            {doc.status === "needs_review" && !readOnly && (
              <Button size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => onEdit(doc)}>
                Review
              </Button>
            )}
          </div>
          {doc.status === "failed" && doc.error && (
            <p className="mt-1.5 text-xs leading-snug text-destructive" role="status">
              {doc.error}
            </p>
          )}
        </div>
        <div className={cn("flex shrink-0 flex-col gap-0.5", readOnly && "hidden")}>
          {doc.status === "ready" && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onEdit(doc)}
              aria-label={`Edit details of ${doc.filename}`}
            >
              <Pencil aria-hidden />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onDelete(doc)}
            aria-label={`Delete ${doc.filename}`}
            disabled={isProcessing(doc.status)}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>
    </li>
  );
}

export function ProjectSidebar({
  readOnly = false,
  projects,
  project,
  documents,
  loadingDocs,
  onSelectProject,
  onRequestCreate,
  onTrySample,
  sampleBusy,
  onUpload,
  onEditDocument,
  onDeleteDocument,
  onDeleteProject,
}: {
  readOnly?: boolean;
  projects: Project[];
  project: Project | null;
  documents: ProjectDocument[];
  loadingDocs: boolean;
  onSelectProject: (id: string) => void;
  onRequestCreate: () => void;
  onTrySample: () => void;
  sampleBusy: boolean;
  onUpload: () => void;
  onEditDocument: (d: ProjectDocument) => void;
  onDeleteDocument: (d: ProjectDocument) => Promise<void>;
  onDeleteProject: (p: Project) => Promise<void>;
}) {
  const selectId = useId();
  const [toDelete, setToDelete] = useState<ProjectDocument | null>(null);
  const [deleteProject, setDeleteProject] = useState(false);

  const ready = documents.filter((d) => d.status === "ready").length;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="space-y-2">
        <Label htmlFor={selectId} className="text-xs tracking-wide text-muted-foreground uppercase">
          Project
        </Label>
        <div className="flex gap-2">
          <Select value={project?.id ?? ""} onValueChange={onSelectProject}>
            <SelectTrigger id={selectId} className="bg-card">
              <SelectValue placeholder="Select a project" />
            </SelectTrigger>
            <SelectContent>
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!readOnly && (
            <Button variant="outline" size="icon" onClick={onRequestCreate} aria-label="Create a new project">
              <Plus aria-hidden />
            </Button>
          )}
        </div>
        {!projects.some((p) => p.is_sample) && (
          <Button variant="secondary" size="sm" className="w-full" onClick={onTrySample} disabled={sampleBusy}>
            <FlaskConical aria-hidden /> {sampleBusy ? "Loading sample…" : "Try sample project"}
          </Button>
        )}
      </div>

      {project && (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Documents <span className="normal-case">({ready} ready)</span>
            </h2>
            {!readOnly && (
              <Button size="sm" onClick={onUpload}>
                <Upload aria-hidden /> Upload
              </Button>
            )}
          </div>
          {project.is_sample && (
            <p className="text-xs text-muted-foreground">
              Fictional sample data. Every person, company and date is invented.
            </p>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {loadingDocs && documents.length === 0 ? (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : documents.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                <p>No documents yet.</p>
                <p className="mt-1">Upload a plan and a few progress updates to start asking questions.</p>
              </div>
            ) : (
              <ul className="space-y-2" aria-live="polite">
                {documents.map((d) => (
                  <DocumentItem key={d.id} doc={d} readOnly={readOnly} onEdit={onEditDocument} onDelete={setToDelete} />
                ))}
              </ul>
            )}
          </div>
          {!readOnly && (
            <Button
              variant="ghost"
              size="sm"
              className={cn("justify-start text-muted-foreground hover:text-destructive")}
              onClick={() => setDeleteProject(true)}
            >
              <Trash2 aria-hidden /> Delete project
            </Button>
          )}
        </div>
      )}

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this document?</AlertDialogTitle>
            <AlertDialogDescription className="break-all">
              {toDelete?.filename} and all of its searchable passages will be removed from this project. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => toDelete && onDeleteDocument(toDelete)}>
              Delete document
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deleteProject} onOpenChange={setDeleteProject}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {project?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              All {documents.length} documents and their search index will be removed. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => project && onDeleteProject(project)}>Delete project</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
