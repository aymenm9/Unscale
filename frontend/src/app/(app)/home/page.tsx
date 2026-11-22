"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { HowTo, TestModePanel } from "@/components/home-panels";
import { Loading, NeedsYou, PageHeader, Progress, Stats, Track, when } from "@/components/ui";
import { api, type Home } from "@/lib/api";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function HomePage() {
  const { data } = useQuery({
    queryKey: ["home"],
    queryFn: () => api<Home>("/home"),
    refetchInterval: (q) => (q.state.data?.running ? 3000 : 15000),
  });
  if (!data) return <Loading />;
  const replies = data.waiting.filter((w) => w.kind === "reply").length;
  const drafts = data.waiting.filter((w) => w.kind === "draft").length;
  const r = data.running;

  return (
    <div className="max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <PageHeader
          title={`${greeting()}`}
          sub={
            replies + drafts
              ? `${replies} ${replies === 1 ? "reply" : "replies"} and ${drafts} ${drafts === 1 ? "draft" : "drafts"} are waiting for you.`
              : "Nothing is waiting for you. The agent is handling the rest."
          }
        />
        <div className="w-full max-w-[340px]">
          {r ? (
            <Link href={`/campaigns/${r.id}`} className="block text-ink no-underline">
              <Progress done={r.progress_done} total={r.progress_total} label={r.name} note={r.message} />
            </Link>
          ) : (
            <p className="text-sm text-muted">
              No search running. <Link href="/campaigns/new">Start a campaign</Link>
            </p>
          )}
        </div>
      </div>

      <Stats
        items={[
          { n: data.stats.found, label: "companies found" },
          { n: data.stats.good, label: "good fit" },
          { n: data.stats.emailed, label: "conversations" },
          { n: data.stats.replies, label: "replies" },
          { n: data.stats.calls, label: "calls booked" },
        ]}
      />

      <div className="mt-9 flex flex-wrap gap-10">
        <section className="min-w-0 flex-[1_1_620px]">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="semi-wide text-[22px] font-extrabold">Where every conversation is</h2>
            <Link href="/inbox" className="font-bold">
              Open conversations
            </Link>
          </div>
          {data.pipeline.length === 0 ? (
            <p className="mt-3 border-t border-rule pt-4 text-ink-2">
              No conversations yet. Approve a first email in <Link href="/review">Approve drafts</Link> to start one.
            </p>
          ) : (
            <div className="mt-2.5 overflow-x-auto">
              <div className="min-w-[720px]">
                <div className="grid grid-cols-[200px_minmax(0,1fr)_200px] gap-6 border-b border-rule py-2 text-[13px] text-muted">
                  <span>Company and contact</span>
                  <span>Where it is</span>
                  <span>Latest</span>
                </div>
                {data.pipeline.map((t) => {
                  const urgent = t.status === "needs_human";
                  const out = t.status === "suppressed";
                  return (
                    <Link
                      key={t.id}
                      href={`/inbox/${t.id}`}
                      className={`grid grid-cols-[200px_minmax(0,1fr)_200px] gap-6 border-b border-rule py-4 text-ink no-underline ${urgent ? "needs-you -mx-3 px-3" : ""} ${out ? "text-muted" : ""}`}
                    >
                      <div>
                        <div className="text-[17px] font-bold">{t.company.name}</div>
                        <div className="text-[13px] text-muted">
                          {t.contact.name ? `${t.contact.name}${t.contact.title ? `, ${t.contact.title}` : ""}` : "Team inbox"}
                        </div>
                        {urgent && (
                          <div className="mt-1.5">
                            <NeedsYou />
                          </div>
                        )}
                      </div>
                      <div className="pt-1">
                        <Track step={t.step} out={out} />
                      </div>
                      <div className="text-sm">
                        <p className="line-clamp-2">{urgent ? t.handoff_reason : t.last_message?.body}</p>
                        <p className="mt-1 text-[13px] text-muted">{when(t.updated_at)}</p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </section>

        <aside className="min-w-[260px] flex-[0_1_320px]">
          <div className="mb-8">
            <TestModePanel firstThreadId={data.pipeline.find((t) => t.status !== "suppressed")?.id} />
          </div>
          <h2 className="semi-wide text-[22px] font-extrabold">Waiting for you</h2>
          <p className="mb-2 text-[13px] text-muted">The agent will not act on these until you do.</p>
          {data.waiting.length === 0 && <p className="border-t border-rule py-3 text-ink-2">All clear.</p>}
          {data.waiting.map((w) => (
            <Link
              key={`${w.kind}-${w.id}`}
              href={w.kind === "reply" ? `/inbox/${w.id}` : `/review#draft-${w.id}`}
              className="flex items-baseline gap-3 border-t border-rule py-3 text-ink no-underline"
            >
              <span
                className={`min-w-[52px] text-center text-[13px] font-bold ${w.kind === "reply" ? "bg-ink px-2 text-yellow" : "border-2 border-ink px-1.5"}`}
              >
                {w.kind === "reply" ? "Reply" : "Draft"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-bold">{w.company}</span>
                <span className="block text-sm text-ink-2">{w.why}</span>
              </span>
            </Link>
          ))}
          <h2 className="semi-wide mt-8 text-[22px] font-extrabold">Next call</h2>
          {data.next_meeting ? (
            <Link href={`/inbox/${data.next_meeting.thread_id}`} className="mt-1 block text-ink no-underline">
              <span className="block font-bold">{data.next_meeting.label}</span>
              <span className="block text-sm">{data.next_meeting.company}</span>
            </Link>
          ) : (
            <p className="mt-1 text-ink-2">No calls booked yet.</p>
          )}
          <div className="mt-8">
            <HowTo />
          </div>
        </aside>
      </div>
    </div>
  );
}
