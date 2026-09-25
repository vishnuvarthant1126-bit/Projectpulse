// Server-side proxy from the browser to the FastAPI backend.
// The backend URL (and any secrets the backend uses) never reach the browser, and the
// backend itself does not need to be exposed outside the Docker network.
import type { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const ALLOWED_ROOTS = new Set(["health", "config", "projects", "documents"]);

export const dynamic = "force-dynamic";
export const maxDuration = 120;

async function proxy(request: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const { path } = await ctx.params;
  if (!path.length || !ALLOWED_ROOTS.has(path[0]) || path.some((p) => p === ".." || p.includes("/"))) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }
  const target = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, BACKEND_URL);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", "application/json");
  // The backend rate-limits the public demo per client; pass the visitor's address through.
  const clientIp = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || request.headers.get("x-real-ip");
  if (clientIp) headers.set("x-forwarded-for", clientIp);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // Required by Node's fetch when streaming a request body (e.g. file uploads).
      ...(hasBody ? { duplex: "half" } : {}),
      cache: "no-store",
      signal: AbortSignal.timeout(115_000),
    } as RequestInit);
    const out = new Headers();
    const ct = upstream.headers.get("content-type");
    if (ct) out.set("content-type", ct);
    return new Response(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: out });
  } catch (err) {
    const timedOut = err instanceof Error && err.name === "TimeoutError";
    return Response.json(
      { detail: timedOut ? "The server took too long to respond." : "The ProjectPulse API is unreachable." },
      { status: timedOut ? 504 : 502 },
    );
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
