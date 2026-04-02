"use client";

import { useEffect, useId, useRef, useState } from "react";

type Props = {
  chart: string;
};

/**
 * Renders query-specific Mermaid (topic path: plan, research, milestones — not agents).
 */
export function TopicDiagram({ chart }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    const trimmed = chart.trim();
    if (!el || !trimmed) return;

    let cancelled = false;
    setError(null);
    el.innerHTML = "";

    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        });
        const { svg } = await mermaid.render(`topic-diagram-${reactId}-${Math.random().toString(36).slice(2, 9)}`, trimmed);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not render diagram");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chart, reactId]);

  if (!chart.trim()) {
    return null;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-xs text-amber-200">
        <p className="font-medium">Diagram render error</p>
        <pre className="mt-2 whitespace-pre-wrap font-mono text-[var(--muted)]">{error}</pre>
        <details className="mt-2 text-[var(--muted)]">
          <summary className="cursor-pointer">Raw Mermaid</summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded bg-[var(--bg)] p-2">{chart}</pre>
        </details>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="topic-diagram flex min-h-[120px] justify-center overflow-x-auto rounded-lg border border-[var(--border)] bg-[#0b1220] p-4 [&_svg]:max-w-full"
    />
  );
}
