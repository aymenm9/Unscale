"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/* The agent runs on free AI providers with daily limits. When every one of them is at its
   limit (or none is set up), say so at the top of every page, with when it comes back,
   instead of letting buttons fail with a bare error code. */

type AiStatus = {
  ok: boolean;
  providers: number;
  resting: number;
  retry_in_seconds: number | null;
  message: string;
};

export default function AiStatusBanner() {
  const status = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api<AiStatus>("/ai-status"),
    refetchInterval: 60_000,
  });
  if (!status.data || status.data.ok) return null;
  return (
    <div role="alert" className="mb-6 border-l-4 border-yellow bg-yellow-soft px-4 py-3">
      <p className="font-extrabold">The AI is paused</p>
      <p className="mt-1 text-sm text-ink-2">{status.data.message}</p>
      <p className="mt-1 text-sm text-muted">
        You can still read, approve and send what is already written. New AI work waits until then.
      </p>
    </div>
  );
}
