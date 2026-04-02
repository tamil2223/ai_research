"use client";

import { useCallback, useState } from "react";
import type { RunResponse } from "@/lib/types";
import { TopicDiagram } from "@/components/TopicDiagram";

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [debug, setDebug] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunResponse | null>(null);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setResult(null);
      setLoading(true);
      try {
        const res = await fetch(`${apiBase()}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: query.trim(),
            ...(sessionId.trim() ? { session_id: sessionId.trim() } : {}),
            debug,
          }),
        });
        const text = await res.text();
        if (!res.ok) {
          setError(text || `${res.status} ${res.statusText}`);
          return;
        }
        setResult(JSON.parse(text) as RunResponse);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [query, sessionId, debug],
  );

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <header className="mb-10">
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Multi-agent research
        </h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Sends your query to <code className="rounded bg-[var(--surface)] px-1 py-0.5 text-xs">POST /run</code>{" "}
          on {apiBase()}
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-[var(--muted)]">Query</span>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            required
            className="w-full resize-y rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-white placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            placeholder="e.g. Analyze AI startup opportunities in 2026"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-[var(--muted)]">
            Session ID <span className="font-normal">(optional)</span>
          </span>
          <input
            type="text"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-white focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            placeholder="optional-session-id"
          />
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--muted)]">
          <input
            type="checkbox"
            checked={debug}
            onChange={(e) => setDebug(e.target.checked)}
            className="rounded border-[var(--border)] bg-[var(--bg)]"
          />
          Debug (verbose traces on server)
        </label>

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="w-full rounded-lg bg-[var(--accent)] py-2.5 text-sm font-medium text-[var(--bg)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Running workflow…" : "Run workflow"}
        </button>
      </form>

      {error && (
        <div
          className="mt-6 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200"
          role="alert"
        >
          {error}
        </div>
      )}

      {result && (
        <div className="mt-8 space-y-6">
          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Meta</h2>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-[var(--muted)]">run_id</dt>
                <dd className="font-mono text-xs break-all">{result.run_id}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">latency_ms</dt>
                <dd>{result.latency_ms}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">cost (Gemini)</dt>
                <dd>
                  {result.cost.tokens} tokens total
                  {typeof result.cost.prompt_tokens === "number" && result.cost.prompt_tokens > 0 ? (
                    <span className="text-[var(--muted)]">
                      {" "}
                      · in {result.cost.prompt_tokens} · out {result.cost.completion_tokens ?? 0}
                    </span>
                  ) : null}
                  {" · "}${result.cost.estimated_usd.toFixed(4)} est.
                </dd>
              </div>
            </dl>
          </section>

          {result.topic_diagram_mermaid ? (
            <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
                Topic diagram
              </h2>
              <p className="mt-1 text-xs text-[var(--muted)]">
                A visual path for your question—how to plan, what to research, skills or milestones, and how to move
                forward—based on the run&apos;s plan and synthesized answer (not the LangGraph agent names).
              </p>
              <div className="mt-4">
                <TopicDiagram chart={result.topic_diagram_mermaid} />
              </div>
            </section>
          ) : null}

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Plan</h2>
            <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
              {result.plan.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Final output</h2>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-white/90">{result.final_output}</p>
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Critique</h2>
            <p className="mt-2 text-sm">
              {result.critique.should_retry && (
                <span className="ml-2 text-amber-300">· retry suggested</span>
              )}
            </p>
            {result.critique.feedback ? (
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--muted)]">{result.critique.feedback}</p>
            ) : null}
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Sources</h2>
            <ul className="mt-3 space-y-3 text-sm">
              {result.sources.map((s, i) => (
                <li key={i} className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
                    <span className="rounded bg-[var(--surface)] px-1.5 py-0.5">{s.type}</span>
                    <span>{s.origin}</span>
                  </div>
                  <p className="mt-2 leading-relaxed text-white/90">{s.snippet}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Trace</h2>
            <ul className="mt-3 space-y-2 font-mono text-xs">
              {result.trace.map((t, i) => (
                <li key={i} className="flex justify-between gap-4 border-b border-[var(--border)] pb-2 last:border-0">
                  <span>{t.node}</span>
                  <span className="text-[var(--muted)]">{t.latency_ms} ms</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Raw JSON</h2>
            <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-[var(--bg)] p-4 text-xs leading-relaxed text-[var(--muted)]">
              {JSON.stringify(
                {
                  ...result,
                  topic_diagram_mermaid: result.topic_diagram_mermaid
                    ? "(Mermaid omitted — see Topic diagram above)"
                    : result.topic_diagram_mermaid,
                },
                null,
                2,
              )}
            </pre>
          </section>
        </div>
      )}
    </main>
  );
}
