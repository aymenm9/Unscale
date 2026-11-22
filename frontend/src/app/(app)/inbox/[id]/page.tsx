"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ACTION, Button, Checks, Loading, PageHeader, ThreadTag, Track, when } from "@/components/ui";
import { api, errorText, post, type Check, type ThreadDetail } from "@/lib/api";

const KIND: Record<string, string> = {
  first: "First email",
  follow_up: "Follow-up",
  reply: "Agent reply",
  manual: "Sent by you",
  confirmation: "Opt-out confirmation",
  inbound: "Their reply",
};

function Compose({ t }: { t: ThreadDetail }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const [comment, setComment] = useState("");
  const [askAi, setAskAi] = useState(false);
  const [changed, setChanged] = useState("");
  const [preview, setPreview] = useState<{ html: string; checks: Check[] } | null>(null);
  const { data: templates } = useQuery({
    queryKey: ["templates", t.id],
    queryFn: () => api<{ key: string; label: string; body: string }[]>(`/threads/${t.id}/templates`),
  });

  // Live preview: re-render half a second after the person stops typing.
  useEffect(() => {
    if (!body.trim()) return;
    const timer = setTimeout(() => {
      post<{ html: string; checks: Check[] }>("/preview", { body, thread_id: t.id }).then(setPreview).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [body, t.id]);

  const send = useMutation({
    mutationFn: () => post(`/threads/${t.id}/send`, { body }),
    onSuccess: () => {
      setBody("");
      setPreview(null);
      qc.invalidateQueries();
    },
  });
  const rewrite = useMutation({
    mutationFn: () => post<{ body: string; what_changed: string }>(`/threads/${t.id}/rewrite`, { body, comment }),
    onSuccess: (r) => {
      setBody(r.body);
      setChanged(r.what_changed);
      setAskAi(false);
      setComment("");
    },
  });
  const failing = preview?.checks.filter((c) => !c.passed) ?? [];

  return (
    <section className="mt-8 border-t-2 border-ink pt-5" aria-label="Write a reply">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="semi-wide text-xl font-extrabold">Write a reply</h2>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Start from</span>
          <select
            className="min-h-10 border-2 border-rule bg-white px-2"
            value=""
            onChange={(e) => {
              const tpl = templates?.find((x) => x.key === e.target.value);
              if (tpl) setBody(tpl.body);
            }}
          >
            <option value="">A template…</option>
            {templates?.map((x) => (
              <option key={x.key} value={x.key}>{x.label}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="mt-1 text-sm text-muted">Sending from here means you take over. The agent stays quiet until you hand it back.</p>

      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={10}
            aria-label="Reply text"
            placeholder={`Hi ${(t.contact.name || "there").split(" ")[0]},`}
            className="w-full border-2 border-ink p-3 leading-relaxed"
          />
          {changed && <p className="mt-1 text-[13px] text-muted">AI changed: {changed}</p>}
          {askAi ? (
            <div className="mt-3 border-l-[3px] border-yellow pl-3">
              <label className="text-sm font-bold" htmlFor="ai-comment">What should change?</label>
              <textarea
                id="ai-comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                placeholder="Shorter, warmer, offer Tuesday instead…"
                className="mt-1 w-full border-2 border-rule p-2"
              />
              <p className="text-[13px] text-muted">The AI sees the whole thread, the sources, the plan and your free slots.</p>
              <div className="mt-2 flex gap-2">
                <Button tone="yellow" onClick={() => rewrite.mutate()} disabled={!comment.trim() || rewrite.isPending}>
                  {rewrite.isPending ? "Rewriting…" : "Rewrite"}
                </Button>
                <Button tone="quiet" onClick={() => setAskAi(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button tone="dark" onClick={() => send.mutate()} disabled={!body.trim() || send.isPending || failing.length > 0}>
                {send.isPending ? "Sending…" : "Send reply"}
              </Button>
              <Button onClick={() => setAskAi(true)}>Rewrite with AI</Button>
            </div>
          )}
          {(send.error || rewrite.error) && <p className="mt-2 text-red" role="alert">{errorText(send.error || rewrite.error)}</p>}
        </div>
        <div>
          <h3 className="text-[13px] text-muted">What they will see</h3>
          {preview && body.trim() ? (
            <>
              <iframe title="Email preview" srcDoc={preview.html} sandbox="" className="mt-1 h-[470px] w-full border border-rule bg-white" />
              <details className="mt-3 text-sm" open={failing.length > 0}>
                <summary className="cursor-pointer text-muted">
                  {failing.length === 0
                    ? `✓ Passed all ${preview.checks.length} safety checks`
                    : `${preview.checks.length - failing.length} of ${preview.checks.length} safety checks passed`}
                </summary>
                <div className="mt-2"><Checks checks={preview.checks} /></div>
              </details>
            </>
          ) : (
            <p className="mt-1 border border-dashed border-rule p-6 text-sm text-muted">Start typing to see the email with signature and unsubscribe link.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function Simulate({ t }: { t: ThreadDetail }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const sim = useMutation({
    mutationFn: () => post<{ action: string; reason: string }>(`/threads/${t.id}/simulate-reply`, { body }),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries();
    },
  });
  const box = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (window.location.hash === "#test-reply" && box.current) {
      box.current.open = true;
      box.current.scrollIntoView({ block: "start" });
    }
  }, []);
  const samples = ["Sounds interesting, what does it cost?", "We already have an accountant.", "Sure, Tuesday works.", "Are you a bot?", "Please stop emailing me."];
  return (
    <details ref={box} id="test-reply" className="mt-8 border-t-2 border-yellow bg-yellow/10 p-4">
      <summary className="cursor-pointer font-bold">Test: reply as the prospect</summary>
      <p className="mt-2 text-sm text-muted">Pretend you are {t.contact.name || "the prospect"} and see what the agent does. Nothing leaves the app.</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {samples.map((s) => (
          <button key={s} onClick={() => setBody(s)} className="border border-rule px-2 py-1 text-sm">{s}</button>
        ))}
      </div>
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} aria-label="Prospect reply" className="mt-2 w-full border-2 border-rule p-2" />
      <Button onClick={() => sim.mutate()} disabled={!body.trim() || sim.isPending} className="mt-2">
        {sim.isPending ? "The agent is reading…" : "Send as prospect"}
      </Button>
      {sim.data && <p className="mt-2 text-sm">Agent: {ACTION[sim.data.action] ?? sim.data.action}. {sim.data.reason}</p>}
      {sim.error && <p className="mt-2 text-red">{errorText(sim.error)}</p>}
    </details>
  );
}

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { data: t } = useQuery({ queryKey: ["thread", id], queryFn: () => api<ThreadDetail>(`/threads/${id}`), refetchInterval: 10000 });
  const act = useMutation({
    mutationFn: (path: string) => post<{ result?: string }>(`/threads/${id}/${path}`),
    onSuccess: () => qc.invalidateQueries(),
  });
  if (!t) return <Loading />;
  const closed = t.status === "suppressed" || t.status === "closed";
  const r = t.report || {};
  const pos = (eid: number) => t.evidence.findIndex((e) => e.id === eid) + 1;

  return (
    <div className="max-w-6xl">
      <PageHeader
        title={t.company.name}
        back={{ href: "/inbox", label: "conversations" }}
        sub={<>{t.contact.name ? `${t.contact.name}${t.contact.title ? `, ${t.contact.title}` : ""}` : "Team inbox"}. <Link href={`/companies/${t.company.id}`}>Company report</Link></>}
      >
        <ThreadTag status={t.status} mode={t.mode} />
      </PageHeader>

      <div className="mt-6 max-w-2xl"><Track step={t.step} out={t.status === "suppressed"} /></div>

      {t.status === "needs_human" && (
        <div className="needs-you mt-6 px-4 py-3">
          <p className="font-bold">The agent stopped and is waiting for you.</p>
          <p className="text-sm">{t.handoff_reason}</p>
          <p className="mt-1 text-sm">Write a reply below, or hand it back if the agent should carry on.</p>
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-2 border-y border-rule py-3 text-sm">
        {t.mode === "agent" && !closed && <Button onClick={() => act.mutate("takeover")}>Take over</Button>}
        {(t.mode === "human" || t.status === "needs_human") && !closed && (
          <Button tone="dark" onClick={() => act.mutate("release")}>Hand back to agent</Button>
        )}
        {t.mode === "agent" && t.status === "open" && t.followups_sent < 3 && (
          <Button tone="quiet" onClick={() => act.mutate("followup-now")}>Send next follow-up now</Button>
        )}
        <span className="text-muted">
          {t.next_followup_at
            ? `Follow-up ${t.followups_sent + 1} of 3 goes out ${new Date(t.next_followup_at.endsWith("Z") ? t.next_followup_at : t.next_followup_at + "Z").toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`
            : `${t.followups_sent} of 3 follow-ups sent. No follow-up scheduled.`}
        </span>
        {act.data?.result && <span className="font-bold">{act.data.result}</span>}
        {act.error && <span className="text-red">{errorText(act.error)}</span>}
      </div>

      <div className="mt-6 grid gap-10 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <ol className="grid gap-6">
            {t.messages.map((m) => (
              <li key={m.id} className={m.direction === "inbound" ? "border-l-[3px] border-blue pl-4" : "border-l-[3px] border-ink pl-4"}>
                <div className="flex flex-wrap items-baseline justify-between gap-2 text-[13px] text-muted">
                  <span>
                    <span className="font-bold text-ink">{KIND[m.kind] ?? m.kind}</span>
                    {m.direction === "outbound" && m.sent_to ? ` to ${m.sent_to}` : ""}
                  </span>
                  <span>{when(m.created_at)}</span>
                </div>
                {m.subject && <p className="mt-1 text-sm font-bold">{m.subject}</p>}
                <p className="mt-1 max-w-[65ch] whitespace-pre-line leading-relaxed">{m.body}</p>
                {m.agent_notes && (
                  <p className="mt-2 bg-rule-soft px-3 py-2 text-[13px] text-ink-2">
                    <span className="font-bold">Agent: {ACTION[m.agent_notes.action] ?? m.agent_notes.action}.</span> {m.agent_notes.reason}
                    {m.agent_notes.analysis && ` (read as "${m.agent_notes.analysis.intent.replace("_", " ")}", ${Math.round(m.agent_notes.analysis.confidence * 100)}% sure)`}
                  </p>
                )}
              </li>
            ))}
          </ol>
          {t.meeting && <p className="mt-6 bg-blue px-4 py-3 font-bold text-white">Call booked for {t.meeting.label}</p>}
          {closed ? (
            <p className="mt-8 border-t-2 border-ink pt-5 text-ink-2">
              {t.status === "suppressed" ? "They opted out. Nobody can email them again." : "This conversation is closed."}
            </p>
          ) : (
            <>
              <Compose t={t} />
              <Simulate t={t} />
            </>
          )}
        </div>

        <aside className="grid content-start gap-6 text-sm">
          <div>
            <h2 className="semi-wide text-lg font-extrabold">What we know</h2>
            <dl className="mt-2 grid gap-2">
              <div><dt className="text-muted">Interest</dt><dd>{r.interest || "No reply yet"}</dd></div>
              {r.pain && <div><dt className="text-muted">Their problem</dt><dd>{r.pain}</dd></div>}
              {r.objections && r.objections.length > 0 && <div><dt className="text-muted">Objections</dt><dd>{r.objections.join("; ")}</dd></div>}
              {r.next_step && <div><dt className="text-muted">Next step</dt><dd>{r.next_step}</dd></div>}
            </dl>
            {r.new_since_last && r.new_since_last.length > 0 && (
              <ul className="mt-2 grid gap-1">
                {r.new_since_last.map((x) => <li key={x}><span className="marked px-1">New: {x}</span></li>)}
              </ul>
            )}
            {r.call_prep && r.call_prep.length > 0 && (
              <div className="mt-3">
                <h3 className="font-bold">Call prep</h3>
                <ul className="mt-1 list-disc pl-5">{r.call_prep.map((x) => <li key={x}>{x}</li>)}</ul>
              </div>
            )}
          </div>
          {t.strategy && (
            <div className="border-t border-rule pt-4">
              <h2 className="semi-wide text-lg font-extrabold">The approved plan</h2>
              <p className="mt-1">{t.strategy.pain}</p>
              <ol className="mt-2 list-decimal pl-5 text-ink-2">
                {t.strategy.follow_up_angles?.map((a) => (
                  <li key={a.step} className={a.step <= t.followups_sent ? "text-muted line-through" : ""}>{a.angle}</li>
                ))}
              </ol>
            </div>
          )}
          <div className="border-t border-rule pt-4">
            <h2 className="semi-wide text-lg font-extrabold">Sources</h2>
            <ol className="mt-1 grid gap-1.5">
              {t.evidence.map((e) => (
                <li key={e.id}>
                  <span className="font-bold tabular-nums">{pos(e.id)}. </span>
                  <a href={e.url} target="_blank" rel="noreferrer">{e.claim}</a>
                </li>
              ))}
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
}
