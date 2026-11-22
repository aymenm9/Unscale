"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button, Checks, Cited, Empty, Loading, PageHeader, Score } from "@/components/ui";
import { api, errorText, post, type Draft } from "@/lib/api";

const VOICE: Record<string, string> = {
  peer_founder: "Peer founder",
  numbers_operator: "Numbers-first operator",
  finance_peer: "Finance peer",
  short_plain: "Short and plain",
};

function DraftCard({ d }: { d: Draft }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(d.subject);
  const [body, setBody] = useState(d.body);
  const [note, setNote] = useState("");
  const done = () => qc.invalidateQueries();
  const approve = useMutation({
    mutationFn: () => post(`/review/${d.id}/approve`, editing ? { subject, body } : {}),
    onSuccess: done,
  });
  const reject = useMutation({ mutationFn: () => post(`/review/${d.id}/reject`, { note }), onSuccess: done });
  const redo = useMutation({ mutationFn: () => post(`/review/${d.id}/redo`), onSuccess: done });
  const failing = d.checks.filter((c) => !c.passed);
  const ev = Object.fromEntries(d.citations.map((c) => [c.id, c]));
  const trigger = ev[d.strategy?.trigger_evidence_id];

  return (
    <article id={`draft-${d.id}`} className="border-t-2 border-ink py-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="semi-wide text-2xl font-extrabold">
            <Link href={`/companies/${d.company.id}`} className="text-ink">{d.company.name}</Link>
          </h2>
          <p className="text-sm text-muted">
            {d.contact.name ? `To ${d.contact.name}${d.contact.title ? `, ${d.contact.title}` : ""}` : "To their team inbox"}
            . Fit <Score value={d.company.score} verdict={d.company.verdict} />
          </p>
        </div>
      </div>
      {(d.handoff_reason || failing.length > 0) && (
        <div className="needs-you mt-3 px-4 py-2 text-sm">
          <span className="font-bold">The agent needs you. </span>
          {d.handoff_reason || `It could not fix this on its own: ${failing.map((c) => c.detail).join(" ")}`}
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-10">
        <div className="min-w-0 flex-[1_1_440px]">
          <h3 className="text-[13px] text-muted">First email</h3>
          {editing ? (
            <>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" className="mt-2 min-h-11 w-full border-2 border-ink px-3 font-bold" />
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} aria-label="Email body" className="mt-2 w-full border-2 border-ink p-3 leading-relaxed" />
              <p className="text-[13px] text-muted">Keep the [1] markers next to facts. They are removed before sending.</p>
            </>
          ) : (
            <div className="mt-2">
              <p className="font-bold">Subject: {d.subject}</p>
              <p className="mt-2 max-w-[62ch] text-base leading-relaxed whitespace-pre-line">
                <Cited body={d.body} citations={d.citations} />
              </p>
            </div>
          )}
          <details className="mt-5 text-sm">
            <summary className="cursor-pointer text-muted">
              {failing.length === 0
                ? `✓ Passed all ${d.checks.length} safety checks`
                : `${d.checks.length - failing.length} of ${d.checks.length} safety checks passed`}
            </summary>
            <div className="mt-2">
              <Checks checks={d.checks} />
            </div>
          </details>
        </div>

        <div className="min-w-[260px] flex-[0_1_360px]">
          <h3 className="text-[13px] text-muted">The plan you approve</h3>
          <dl className="mt-2 grid gap-3 text-sm">
            <div><dt className="text-muted">Voice</dt><dd className="font-bold">{VOICE[d.strategy?.voice] ?? d.strategy?.voice}</dd></div>
            <div><dt className="text-muted">Opens with</dt><dd>{trigger ? trigger.claim : "—"}</dd></div>
            <div><dt className="text-muted">The problem we bet on</dt><dd>{d.strategy?.pain}</dd></div>
            <div>
              <dt className="text-muted">Follow-ups if no reply (day 3, 7, 11)</dt>
              <dd>
                <ol className="list-decimal pl-5">
                  {d.strategy?.follow_up_angles?.map((a) => <li key={a.step}>{a.angle}</li>)}
                </ol>
              </dd>
            </div>
            {d.strategy?.avoid?.length > 0 && <div><dt className="text-muted">Will not mention</dt><dd>{d.strategy.avoid.join(", ")}</dd></div>}
          </dl>
          <h3 className="mt-5 text-[13px] text-muted">Sources</h3>
          <ol className="mt-1 grid list-decimal gap-1.5 pl-5 text-sm">
            {d.citations.map((c) => (
              <li key={c.id}>
                <a href={c.url} target="_blank" rel="noreferrer">{c.claim}</a>
                <div className="text-[13px] text-muted">“{c.quote}”</div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {(approve.error || reject.error || redo.error) && (
        <p className="mt-4 text-red" role="alert">{errorText(approve.error || reject.error || redo.error)}</p>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <Button tone="dark" onClick={() => approve.mutate()} disabled={approve.isPending}>
          {editing ? "Save and send" : "Approve and send"}
        </Button>
        <Button onClick={() => setEditing(!editing)}>{editing ? "Cancel edit" : "Edit"}</Button>
        <Button tone="quiet" onClick={() => redo.mutate()} disabled={redo.isPending}>
          {redo.isPending ? "The agent is rewriting…" : "Ask the agent to redo"}
        </Button>
        <span className="mx-2 hidden h-6 border-l border-rule md:block" />
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why reject? (optional)" aria-label="Reject reason" className="min-h-11 min-w-[200px] flex-1 border-2 border-rule px-3" />
        <Button tone="quiet" onClick={() => reject.mutate()} disabled={reject.isPending}>Reject</Button>
      </div>
      <p className="mt-2 text-[13px] text-muted">Approving sends this email and lets the agent follow up and reply on this plan. It stops and asks you when unsure.</p>
    </article>
  );
}

export default function Review() {
  const { data } = useQuery({ queryKey: ["review"], queryFn: () => api<Draft[]>("/review") });
  if (!data) return <Loading />;
  return (
    <div className="max-w-6xl">
      <PageHeader title="Approve drafts" sub="Approve the plan and the first email once. After that the agent works alone until it needs you." />
      <div className="mt-7">
        {data.length === 0 ? (
          <Empty>
            No drafts waiting. <Link href="/campaigns/new">Start a campaign</Link> to get new ones.
          </Empty>
        ) : (
          data.map((d) => <DraftCard key={d.id} d={d} />)
        )}
      </div>
    </div>
  );
}
