"use client";

import { useCallback, useState } from "react";
import type { RunResponse } from "@/lib/types";

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
    <main className="mx-auto max-w-3xl px-4 py-10">
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
                <dt className="text-[var(--muted)]">cost</dt>
                <dd>
                  {result.cost.tokens} tokens · ${result.cost.estimated_usd.toFixed(4)}
                </dd>
              </div>
            </dl>
          </section>

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
            <div className="mt-3 space-y-3 text-sm">
              {typeof result.final_output.summary === "string" && (
                <p className="leading-relaxed">{result.final_output.summary}</p>
              )}
              {Array.isArray(result.final_output.insights) && (
                <div>
                  <div className="text-xs font-medium text-[var(--muted)]">Insights</div>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {(result.final_output.insights as string[]).map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                </div>
              )}
              {Array.isArray(result.final_output.recommendations) && (
                <div>
                  <div className="text-xs font-medium text-[var(--muted)]">Recommendations</div>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {(result.final_output.recommendations as string[]).map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                </div>
              )}
              {Array.isArray(result.final_output.evidence_snippets) &&
                (result.final_output.evidence_snippets as string[]).length > 0 && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-[var(--muted)]">Evidence snippets</summary>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-[var(--muted)]">
                      {(result.final_output.evidence_snippets as string[]).map((x, i) => (
                        <li key={i}>{x}</li>
                      ))}
                    </ul>
                  </details>
                )}
            </div>
          </section>

          <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Critique</h2>
            <p className="mt-2 text-sm">
              <span className="font-medium">{result.critique.verdict}</span>
              {result.critique.should_retry && (
                <span className="ml-2 text-amber-300">· retry suggested</span>
              )}
            </p>
            {result.critique.reasons.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
                {result.critique.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
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
              {JSON.stringify(result, null, 2)}
            </pre>
          </section>
        </div>
      )}
    </main>
  );
}
