"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Loading, PageHeader, Score, ThreadTag, Track, when } from "@/components/ui";
import { api, type CompanyRow, type Evidence, type Qualification, type ThreadRow } from "@/lib/api";

type CompanyDetail = CompanyRow & {
  summary: string;
  qualification: Qualification | null;
  evidence: Evidence[];
  contacts: { id: number; name: string; title: string; email: string; source_url: string }[];
  drafts: { id: number; status: string; subject: string }[];
  threads: ThreadRow[];
};

function Reasons({ title, items, evidence }: { title: string; items: Qualification["reasons"]; evidence: Evidence[] }) {
  if (!items.length) return null;
  const pos = (id: number) => evidence.findIndex((e) => e.id === id) + 1;
  return (
    <div>
      <h3 className="text-[13px] text-muted">{title}</h3>
      <ul className="mt-1 grid gap-2">
        {items.map((r, i) => (
          <li key={i} className="flex gap-3 border-b border-rule-soft pb-2">
            <span className="w-10 shrink-0 font-bold tabular-nums">{r.points > 0 ? `+${r.points}` : r.points}</span>
            <span>
              {r.text}{" "}
              {r.evidence_ids.map((id) => (
                <a key={id} href={`#source-${id}`} className="align-super text-[11px] font-bold">
                  [{pos(id)}]
                </a>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CompanyPage() {
  const { id } = useParams<{ id: string }>();
  const { data: c } = useQuery({ queryKey: ["company", id], queryFn: () => api<CompanyDetail>(`/companies/${id}`) });
  if (!c) return <Loading />;
  const q = c.qualification;
  const thread = c.threads[0];
  const draft = c.drafts.find((d) => d.status === "pending");
  const step = thread ? thread.step : q ? 2 : 1;

  return (
    <div className="max-w-5xl">
      <PageHeader
        title={c.name}
        back={c.campaign_id ? { href: `/campaigns/${c.campaign_id}`, label: "campaign" } : { href: "/companies", label: "companies" }}
        sub={
          <>
            <a href={`https://${c.domain}`} target="_blank" rel="noreferrer">{c.domain}</a>
            {c.location ? `, ${c.location}` : ""}
            {c.channels?.length ? `. Sells on ${c.channels.join(", ")}` : ""}
          </>
        }
      >
        {draft && <Link href={`/review#draft-${draft.id}`} className="inline-flex min-h-11 items-center bg-yellow px-4 font-bold text-ink no-underline">Review draft</Link>}
        {thread && <Link href={`/inbox/${thread.id}`} className="inline-flex min-h-11 items-center border-2 border-ink px-4 text-ink no-underline">Read conversation</Link>}
      </PageHeader>

      <div className="mt-7 max-w-2xl">
        <Track step={step} out={thread?.status === "suppressed" || q?.verdict === "poor"} />
      </div>

      <section className="mt-9 grid gap-8 border-t-2 border-ink pt-6 md:grid-cols-[1fr_280px]">
        <div className="grid gap-6">
          <div className="flex items-baseline gap-3">
            <Score value={c.score} verdict={c.verdict} />
            <p className="text-[17px]">{q?.summary || c.summary || "Not qualified yet."}</p>
          </div>
          {q && (
            <>
              <Reasons title="Why it fits" items={q.reasons.filter((r) => r.points > 0)} evidence={c.evidence} />
              <Reasons title="Why it might not" items={q.reasons.filter((r) => r.points <= 0)} evidence={c.evidence} />
              {q.confidence < 0.6 && <p className="needs-you px-4 py-2 text-sm">The agent is not sure about this one ({Math.round(q.confidence * 100)}% confident). Check the sources.</p>}
            </>
          )}
        </div>
        <dl className="grid content-start gap-3 text-sm">
          <div><dt className="text-muted">Revenue</dt><dd>{c.revenue_band || "Unknown"}{c.revenue_confidence === "low" ? " (a guess)" : ""}</dd></div>
          <div><dt className="text-muted">Team size</dt><dd>{c.employee_band || "Unknown"}{c.employee_confidence === "low" ? " (a guess)" : ""}</dd></div>
          <div><dt className="text-muted">Platform</dt><dd>{c.platform || "Unknown"}</dd></div>
          <div>
            <dt className="text-muted">Who we would email</dt>
            {c.contacts.length ? (
              c.contacts.map((p) => (
                <dd key={p.id}>
                  <span className="font-bold">{p.name || "Team inbox"}</span>
                  {p.title ? `, ${p.title}` : ""}
                  <div className="text-[13px] text-muted">{p.email}</div>
                </dd>
              ))
            ) : (
              <dd>Not found yet</dd>
            )}
          </div>
        </dl>
      </section>

      <section className="mt-9 border-t-2 border-ink pt-6">
        <h2 className="semi-wide text-xl font-extrabold">Sources</h2>
        <p className="text-sm text-muted">Every fact the agent uses comes from one of these pages, quoted word for word.</p>
        <ol className="mt-4 grid gap-4">
          {c.evidence.map((e, i) => (
            <li key={e.id} id={`source-${e.id}`} className="grid grid-cols-[32px_1fr] gap-2 border-b border-rule-soft pb-3">
              <span className="font-bold tabular-nums">{i + 1}</span>
              <div>
                <div className="font-bold">{e.claim}</div>
                <blockquote className="mt-1 border-l-[3px] border-yellow pl-3 text-ink-2">“{e.quote}”</blockquote>
                <a href={e.url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[13px] break-all">{e.url}</a>
                <span className="text-[13px] text-muted"> Read {when(e.fetched_at)}</span>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {c.threads.length > 0 && (
        <section className="mt-9 border-t-2 border-ink pt-6">
          <h2 className="semi-wide text-xl font-extrabold">Conversations</h2>
          <ul className="mt-3">
            {c.threads.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-rule py-3">
                <Link href={`/inbox/${t.id}`} className="font-bold">{t.subject}</Link>
                <ThreadTag status={t.status} mode={t.mode} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
