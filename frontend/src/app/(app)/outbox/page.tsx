"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ACTION, Button, Empty, Loading, PageHeader, when } from "@/components/ui";
import { api, errorText, post, type OutboxItem } from "@/lib/api";

export default function Outbox() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["outbox"], queryFn: () => api<OutboxItem[]>("/outbox"), refetchInterval: 10000 });
  const [openId, setOpenId] = useState<number | null>(null);
  const [reply, setReply] = useState("");
  const sim = useMutation({
    mutationFn: (threadId: number) => post<{ action: string; reason: string }>(`/threads/${threadId}/simulate-reply`, { body: reply }),
    onSuccess: () => {
      setReply("");
      qc.invalidateQueries();
    },
  });
  if (!data) return <Loading />;
  const open = data.find((m) => m.id === openId) ?? data[0];

  return (
    <div className="max-w-6xl">
      <PageHeader
        title="Test inbox"
        sub="Every email the app sends goes to this demo inbox, never to a real company. Open one and reply as the prospect to see what the agent does."
      />
      {data.length === 0 ? (
        <div className="mt-7"><Empty>No emails yet. Approve a draft to send the first one.</Empty></div>
      ) : (
        <div className="mt-7 grid gap-6 border-t-2 border-ink pt-4 lg:grid-cols-[340px_1fr]">
          <ul className="max-h-[70vh] overflow-y-auto">
            {data.map((m) => (
              <li key={m.id}>
                <button
                  onClick={() => setOpenId(m.id)}
                  className={`w-full border-b border-rule px-2 py-3 text-left ${open?.id === m.id ? "bg-yellow-soft" : ""}`}
                >
                  <div className="flex justify-between gap-2 text-[13px] text-muted">
                    <span>{m.direction === "inbound" ? `From ${m.contact.name || m.contact.email}` : `To ${m.contact.name || m.company}`}</span>
                    <span>{when(m.created_at)}</span>
                  </div>
                  <div className="truncate font-bold">{m.subject}</div>
                  <div className="truncate text-sm text-ink-2">{m.company}</div>
                </button>
              </li>
            ))}
          </ul>
          {open && (
            <div className="min-w-0">
              <dl className="grid grid-cols-[70px_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="text-muted">Subject</dt><dd className="font-bold">{open.subject}</dd>
                <dt className="text-muted">To</dt>
                <dd>
                  {open.direction === "outbound" ? (
                    <>{open.sent_to} <span className="text-muted">(would be {open.contact.email})</span></>
                  ) : "Ledgerwise"}
                </dd>
              </dl>
              {open.direction === "outbound" ? (
                <iframe title="Email" srcDoc={open.html} sandbox="" className="mt-3 h-[380px] w-full border border-rule bg-white" />
              ) : (
                <p className="mt-3 border-l-[3px] border-blue pl-4 whitespace-pre-line">{open.text}</p>
              )}
              {open.direction === "outbound" && open.thread_status !== "suppressed" && open.thread_status !== "closed" && (
                <div className="mt-4">
                  <label htmlFor="sim" className="font-bold">Reply as {open.contact.name || "the prospect"}</label>
                  <textarea id="sim" value={reply} onChange={(e) => setReply(e.target.value)} rows={4} className="mt-1 w-full border-2 border-ink p-3" placeholder="Sounds good, can we talk Tuesday?" />
                  <Button tone="dark" className="mt-2" disabled={!reply.trim() || sim.isPending} onClick={() => sim.mutate(open.thread_id)}>
                    {sim.isPending ? "The agent is reading…" : "Send reply"}
                  </Button>
                  {sim.data && <p className="mt-2 text-sm">Agent: {ACTION[sim.data.action] ?? sim.data.action}. {sim.data.reason}</p>}
                  {sim.error && <p className="mt-2 text-red">{errorText(sim.error)}</p>}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
