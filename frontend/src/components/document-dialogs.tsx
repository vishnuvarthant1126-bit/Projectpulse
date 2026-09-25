"use client";

import { CalendarDays, Upload } from "lucide-react";
import { useId, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { DOC_TYPE_LABELS, type AppConfig, type DocType, type ProjectDocument } from "@/lib/types";

const DOC_TYPES = Object.keys(DOC_TYPE_LABELS) as DocType[];

function DocTypeSelect({ id, value, onChange }: { id: string; value: DocType | ""; onChange: (v: DocType) => void }) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as DocType)}>
      <SelectTrigger id={id} aria-required>
        <SelectValue placeholder="Choose a document type" />
      </SelectTrigger>
      <SelectContent>
        {DOC_TYPES.map((t) => (
          <SelectItem key={t} value={t}>
            {DOC_TYPE_LABELS[t]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

interface UploadProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  projectId: string;
  config: AppConfig | null;
  onUploaded: (doc: ProjectDocument) => void;
}

export function UploadDialog(props: UploadProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent>
        {/* Mounted only while open, so the form state resets every time. */}
        <UploadForm {...props} />
      </DialogContent>
    </Dialog>
  );
}

function UploadForm({ onOpenChange, projectId, config, onUploaded }: UploadProps) {
  const ids = { file: useId(), type: useId(), date: useId() };
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<DocType | "">("");
  const [date, setDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const allowed = config?.allowed_extensions ?? [".pdf", ".md", ".markdown", ".txt"];
  const maxMb = config?.max_upload_mb ?? 10;

  function pick(f: File | null) {
    setError(null);
    if (!f) return setFile(null);
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) return setError(`Unsupported file type. Upload ${allowed.join(", ")} files.`);
    if (f.size > maxMb * 1024 * 1024) return setError(`That file is ${formatBytes(f.size)}; the limit is ${maxMb} MB.`);
    setFile(f);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !docType) return setError("Choose a file and a document type.");
    setBusy(true);
    setError(null);
    try {
      const doc = await api.upload(projectId, file, docType, date || null);
      onUploaded(doc);
      onOpenChange(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>Upload a document</DialogTitle>
        <DialogDescription>
          PDF, Markdown or text, up to {maxMb} MB. Files stay on this machine and are only searchable inside this
          project.
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-2">
        <Label htmlFor={ids.file}>File</Label>
        <Input
          id={ids.file}
          type="file"
          accept={allowed.join(",")}
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
          required
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor={ids.type}>Document type</Label>
        <DocTypeSelect id={ids.type} value={docType} onChange={setDocType} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor={ids.date}>Reporting date (optional now)</Label>
        <Input id={ids.date} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <p className="text-xs text-muted-foreground">
          The date the document reports on, such as the week-ending date or the meeting date. Leave it blank and
          ProjectPulse will suggest a date from the text for you to confirm. Upload time is never used.
        </p>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy || !file || !docType}>
          <Upload aria-hidden /> {busy ? "Uploading…" : "Upload"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Confirm (for documents awaiting review) or edit a document's type and reporting date. */
export function DocumentDetailsDialog({
  doc,
  onOpenChange,
  onSaved,
}: {
  doc: ProjectDocument | null;
  onOpenChange: (o: boolean) => void;
  onSaved: (doc: ProjectDocument) => void;
}) {
  return (
    <Dialog open={!!doc} onOpenChange={onOpenChange}>
      <DialogContent>
        {doc && <DetailsForm key={doc.id} doc={doc} onOpenChange={onOpenChange} onSaved={onSaved} />}
      </DialogContent>
    </Dialog>
  );
}

function DetailsForm({
  doc,
  onOpenChange,
  onSaved,
}: {
  doc: ProjectDocument;
  onOpenChange: (o: boolean) => void;
  onSaved: (doc: ProjectDocument) => void;
}) {
  const ids = { type: useId(), date: useId() };
  const [docType, setDocType] = useState<DocType | "">(doc.doc_type);
  // Pre-filled with the detected date as a suggestion; the user must confirm it.
  const [date, setDate] = useState(doc.reporting_date ?? doc.detected_date ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const reviewing = doc.status === "needs_review";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!docType || !date) return setError("Choose a document type and confirm the reporting date.");
    setBusy(true);
    try {
      onSaved(await api.updateDocument(doc.id, { doc_type: docType, reporting_date: date }));
      onOpenChange(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{reviewing ? "Confirm document details" : "Edit document details"}</DialogTitle>
        <DialogDescription className="break-all">{doc.filename}</DialogDescription>
      </DialogHeader>
      {reviewing && (
        <Alert variant="info">
          <CalendarDays aria-hidden />
          <AlertDescription>
            {doc.detected_date ? (
              <p>
                Suggested from the document text: <q className="font-medium">{doc.detected_date_source}</q>. Check it
                before confirming. The document becomes searchable after you confirm.
              </p>
            ) : (
              <p>No date was found in the document. Enter the date it reports on to make it searchable.</p>
            )}
          </AlertDescription>
        </Alert>
      )}
      <div className="grid gap-2">
        <Label htmlFor={ids.type}>Document type</Label>
        <DocTypeSelect id={ids.type} value={docType} onChange={setDocType} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor={ids.date}>Reporting date</Label>
        <Input id={ids.date} type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy || !date || !docType}>
          {busy ? "Saving…" : reviewing ? "Confirm and index" : "Save"}
        </Button>
      </DialogFooter>
    </form>
  );
}

interface CreateProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreate: (name: string) => Promise<void>;
}

export function CreateProjectDialog(props: CreateProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent>
        <CreateForm {...props} />
      </DialogContent>
    </Dialog>
  );
}

function CreateForm({ onOpenChange, onCreate }: CreateProps) {
  const nameId = useId();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <form
      className="grid gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim()) return;
        setBusy(true);
        try {
          await onCreate(name.trim());
          onOpenChange(false);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <DialogHeader>
        <DialogTitle>New project</DialogTitle>
        <DialogDescription>Documents and questions are kept separate for each project.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-2">
        <Label htmlFor={nameId}>Project name</Label>
        <Input id={nameId} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required autoFocus />
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button type="submit" disabled={!name.trim() || busy}>
          Create project
        </Button>
      </DialogFooter>
    </form>
  );
}
