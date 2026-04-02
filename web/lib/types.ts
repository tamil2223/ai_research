export type RunResponse = {
  run_id: string;
  plan: string[];
  final_output: Record<string, unknown>;
  critique: {
    verdict: "pass" | "needs_improvement";
    reasons: string[];
    should_retry: boolean;
  };
  sources: Array<{
    type: "rag" | "tool";
    origin: string;
    snippet: string;
    metadata?: Record<string, unknown>;
  }>;
  trace: Array<{ node: string; latency_ms: number; detail?: Record<string, unknown> }>;
  tool_calls: Array<{ tool: string; query: string }>;
  cost: {
    tokens: number;
    estimated_usd: number;
    prompt_tokens?: number;
    completion_tokens?: number;
  };
  latency_ms: number;
  /** Mermaid: visual path for the user's topic (goals, research, execution) */
  topic_diagram_mermaid?: string;
};
