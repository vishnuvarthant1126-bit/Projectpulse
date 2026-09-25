"use client";

import { Activity, CircleAlert, CodeXml, Eye, FlaskConical, Menu, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api, ApiError } from "@/lib/api";
import { REPO_URL } from "@/lib/site";
import { isProcessing } from "@/lib/format";
import type { AppConfig, Passage, Project, ProjectDocument, RetrievalMode } from "@/lib/types";

import { ChatPanel, type ChatMessage } from "./chat-panel";
import { CreateProjectDialog, DocumentDetailsDialog, UploadDialog } from "./document-dialogs";
import { Landing } from "./landing";
import { ProjectSidebar } from "./project-sidebar";
import { SourceViewer } from "./source-viewer";

function readProjectFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("project");
}

function writeProjectToUrl(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("project", id);
  else url.searchParams.delete("project");
  window.history.replaceState(null, "", url);
}

export function Dashboard() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  // Documents are stored with the project they belong to, so switching projects never shows stale rows.
  const [docsState, setDocsState] = useState<{ pid: string | null; docs: ProjectDocument[] }>({ pid: null, docs: [] });
  const [suggestionState, setSuggestionState] = useState<{
    pid: string;
    questions: string[];
    precomputed: boolean;
  } | null>(null);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [initialised, setInitialised] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null);
  const [waking, setWaking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [sampleBusy, setSampleBusy] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailsDoc, setDetailsDoc] = useState<ProjectDocument | null>(null);
  const [sourcePassage, setSourcePassage] = useState<Passage | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const project = useMemo(() => projects.find((p) => p.id === projectId) ?? null, [projects, projectId]);
  const documents = useMemo(
    () => (projectId && docsState.pid === projectId ? docsState.docs : []),
    [docsState, projectId],
  );
  const loadingDocs = !!projectId && docsState.pid !== projectId;
  const suggestions =
    suggestionState && suggestionState.pid === projectId ? suggestionState : { questions: [], precomputed: false };

  const selectProject = useCallback((id: string | null) => {
    setProjectId(id);
    writeProjectToUrl(id);
    setNavOpen(false);
  }, []);

  // Initial load
  // Initial load. Free hosting puts the API to sleep when idle, so retry for up to ~2.5 minutes
  // while it wakes up instead of failing on the first request.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const started = Date.now();
      for (let attempt = 0; !cancelled; attempt++) {
        try {
          const [cfg, list] = await Promise.all([api.config(), api.projects()]);
          if (cancelled) return;
          setConfig(cfg);
          setProjects(list);
          const fromUrl = readProjectFromUrl();
          if (fromUrl && list.some((p) => p.id === fromUrl)) setProjectId(fromUrl);
          setWaking(false);
          break;
        } catch (e) {
          const status = e instanceof ApiError ? e.status : 0;
          const retryable = status === 0 || status === 502 || status === 503 || status === 504;
          if (!retryable || Date.now() - started > 150_000) {
            if (!cancelled) setFatal((e as Error).message);
            break;
          }
          if (!cancelled) setWaking(true);
          await new Promise((r) => setTimeout(r, Math.min(3000 + attempt * 1000, 8000)));
        }
      }
      if (!cancelled) setInitialised(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshDocuments = useCallback(async (pid: string) => {
    try {
      const docs = await api.documents(pid);
      setDocsState({ pid, docs });
      setProjects((ps) => ps.map((p) => (p.id === pid ? { ...p, document_count: docs.length } : p)));
    } catch (e) {
      setNotice((e as Error).message);
    }
  }, []);

  // Documents + suggestions for the selected project
  useEffect(() => {
    if (!projectId) return;
    const pid = projectId;
    api
      .documents(pid)
      .then((docs) => setDocsState({ pid, docs }))
      .catch((e: Error) => setNotice(e.message));
    api
      .suggested(pid)
      .then((res) => setSuggestionState({ pid, ...res }))
      .catch(() => setSuggestionState({ pid, questions: [], precomputed: false }));
  }, [projectId]);

  // Poll while any document is still processing
  const processing = documents.some((d) => isProcessing(d.status));
  useEffect(() => {
    if (!projectId || !processing) return;
    const t = setInterval(() => refreshDocuments(projectId), 1200);
    return () => clearInterval(t);
  }, [projectId, processing, refreshDocuments]);

  async function trySample() {
    setSampleBusy(true);
    setNotice(null);
    try {
      const p = await api.sampleProject();
      setProjects((ps) => [p, ...ps.filter((x) => x.id !== p.id)]);
      selectProject(p.id);
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setSampleBusy(false);
    }
  }

  async function createProject(name: string) {
    const p = await api.createProject(name);
    setProjects((ps) => [...ps, p]);
    selectProject(p.id);
  }

  async function deleteProject(p: Project) {
    try {
      await api.deleteProject(p.id);
      setProjects((ps) => ps.filter((x) => x.id !== p.id));
      setMessages((m) => {
        const next = { ...m };
        delete next[p.id];
        return next;
      });
      selectProject(null);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  async function deleteDocument(d: ProjectDocument) {
    try {
      await api.deleteDocument(d.id);
      await refreshDocuments(d.project_id);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  const ask = useCallback(
    async (question: string, mode: RetrievalMode, existingId?: string) => {
      if (!projectId) return;
      const pid = projectId;
      const id = existingId ?? crypto.randomUUID();
      const pending: ChatMessage = { id, question, mode, status: "loading" };
      setMessages((all) => {
        const list = all[pid] ?? [];
        return {
          ...all,
          [pid]: existingId ? list.map((m) => (m.id === id ? pending : m)) : [...list, pending],
        };
      });
      const update = (patch: Partial<ChatMessage>) =>
        setMessages((all) => ({ ...all, [pid]: (all[pid] ?? []).map((m) => (m.id === id ? { ...m, ...patch } : m)) }));
      try {
        const response = await api.ask(pid, question, mode);
        update({ status: "done", response });
      } catch (e) {
        update({ status: "error", error: (e as Error).message });
      }
    },
    [projectId],
  );

  const readyCount = documents.filter((d) => d.status === "ready").length;
  const pendingCount = documents.filter((d) => d.status !== "ready" && d.status !== "failed").length;

  const readOnly = !!config?.public_demo;

  const sidebar = (
    <ProjectSidebar
      readOnly={readOnly}
      projects={projects}
      project={project}
      documents={documents}
      loadingDocs={loadingDocs}
      onSelectProject={selectProject}
      onRequestCreate={() => {
        setNavOpen(false);
        setCreateOpen(true);
      }}
      onTrySample={trySample}
      sampleBusy={sampleBusy}
      onUpload={() => setUploadOpen(true)}
      onEditDocument={setDetailsDoc}
      onDeleteDocument={deleteDocument}
      onDeleteProject={deleteProject}
    />
  );

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-3 border-b bg-card px-4 py-3 md:px-6">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setNavOpen(true)}
          aria-label="Open projects and documents"
        >
          <Menu aria-hidden />
        </Button>
        <button
          type="button"
          onClick={() => selectProject(null)}
          className="flex items-center gap-2 rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Activity className="size-4" aria-hidden />
          </span>
          <span className="text-left leading-tight">
            <span className="block font-semibold">ProjectPulse</span>
            <span className="hidden text-xs text-muted-foreground sm:block">Ask your project what changed</span>
          </span>
        </button>
        <div className="ml-auto flex items-center gap-2">
          {project && <span className="hidden max-w-56 truncate text-sm font-medium lg:inline">{project.name}</span>}
          <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
              <CodeXml aria-hidden /> Source
            </a>
          </Button>
          {config &&
            (config.llm_enabled ? (
              <Badge variant="info" title={`Answers generated by ${config.llm_model}`}>
                <Sparkles aria-hidden /> Live answers
              </Badge>
            ) : (
              <Badge variant="warning" title="No answer model configured: precomputed demo answers and evidence only">
                <FlaskConical aria-hidden /> Demo mode
              </Badge>
            ))}
        </div>
      </header>

      {fatal ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <Alert variant="destructive" className="max-w-lg">
            <CircleAlert aria-hidden />
            <AlertDescription>
              <p>{fatal}</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={() => window.location.reload()}>
                Reload
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <aside className="hidden w-80 shrink-0 border-r bg-muted/30 p-4 md:block" aria-label="Projects and documents">
            {initialised && sidebar}
          </aside>

          <main className="flex min-w-0 flex-1 flex-col" id="main">
            {notice && (
              <div className="px-4 pt-3 md:px-8">
                <Alert variant="destructive">
                  <CircleAlert aria-hidden />
                  <AlertDescription className="flex flex-row flex-wrap items-center justify-between gap-2">
                    <span>{notice}</span>
                    <Button size="sm" variant="ghost" onClick={() => setNotice(null)}>
                      Dismiss
                    </Button>
                  </AlertDescription>
                </Alert>
              </div>
            )}
            {readOnly && (
              <div className="border-b bg-info-muted/60 px-4 py-2 text-xs text-info-foreground md:px-8" role="note">
                <Eye className="mr-1.5 inline size-3.5 align-[-2px]" aria-hidden />
                Public demo: read-only, fictional sample data. To upload your own documents,{" "}
                <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="font-medium underline">
                  run ProjectPulse locally
                </a>
                .
              </div>
            )}
            {!initialised ? (
              <div
                className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground"
                role="status"
              >
                <Activity className="size-5 animate-pulse text-primary" aria-hidden />
                {waking ? (
                  <>
                    <p className="font-medium text-foreground">Waking up the demo server…</p>
                    <p>It runs on free hosting that sleeps when idle, so the first visit can take up to a minute.</p>
                  </>
                ) : (
                  <p>Loading…</p>
                )}
              </div>
            ) : project ? (
              <ChatPanel
                key={project.id}
                messages={messages[project.id] ?? []}
                suggestions={suggestions.questions}
                suggestionsPrecomputed={suggestions.precomputed}
                readyCount={readyCount}
                pendingCount={pendingCount}
                onAsk={(q, m) => ask(q, m)}
                onRetry={(m) => ask(m.question, m.mode, m.id)}
                onOpenSource={setSourcePassage}
              />
            ) : (
              <Landing
                readOnly={readOnly}
                onTrySample={trySample}
                onCreate={() => setCreateOpen(true)}
                sampleBusy={sampleBusy}
                demoMode={!!config?.demo_mode}
              />
            )}
          </main>
        </div>
      )}

      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" className="p-4 pt-12 md:max-w-sm">
          <SheetHeader className="sr-only">
            <SheetTitle>Projects and documents</SheetTitle>
            <SheetDescription>Select a project, upload documents, or review processing status.</SheetDescription>
          </SheetHeader>
          {sidebar}
        </SheetContent>
      </Sheet>

      {project && (
        <UploadDialog
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          projectId={project.id}
          config={config}
          onUploaded={() => refreshDocuments(project.id)}
        />
      )}
      <DocumentDetailsDialog
        doc={detailsDoc}
        onOpenChange={(o) => !o && setDetailsDoc(null)}
        onSaved={() => project && refreshDocuments(project.id)}
      />
      <CreateProjectDialog open={createOpen} onOpenChange={setCreateOpen} onCreate={createProject} />
      <SourceViewer passage={sourcePassage} onClose={() => setSourcePassage(null)} />
    </div>
  );
}
