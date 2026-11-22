"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Bars, Empty, Loading, PageHeader, Tabs, ThreadTag, when } from "@/components/ui";
import { api, type ThreadRow } from "@/lib/api";

type Filter = "all" | "needs" | "agent" | "booked" | "done";

const MATCH: Record<Filter, (t: ThreadRow) => boolean> = {
  all: () => true,
  needs: (t) => t.status === "needs_human",
  agent: (t) => t.status === "open",
  booked: (t) => t.status === "booked",
  done: (t) => t.status === "closed" || t.status === "suppressed",
};

export default function Inbox() {
  const [filter, setFilter] = useState<Filter>("all");
  const { data } = useQuery({ queryKey: ["threads"], queryFn: () => api<ThreadRow[]>("/threads"), refetchInterval: 10000 });
  if (!data) return <Loading />;
  const sorted = [...data].sort(
    (a, b) => Number(b.status === "needs_human") - Number(a.status === "needs_human") || b.updated_at.localeCompare(a.updated_at),
  );
  const rows = sorted.filter(MATCH[filter]);
  const n = (f: Filter) => data.filter(MATCH[f]).length;

  return (
    <div className="max-w-5xl">
      <PageHeader title="Conversations" sub="The agent answers on its own. Threads that need you are on top." />
      <div className="mt-7">
        <Tabs
          value={filter}
          onChange={setFilter}
          items={[
            { key: "all", label: `All ${n("all")}` },
            { key: "needs", label: `Needs you ${n("needs")}` },
            { key: "agent", label: `Agent handling ${n("agent")}` },
            { key: "booked", label: `Call booked ${n("booked")}` },
            { key: "done", label: `Closed ${n("done")}` },
          ]}
        />
      </div>
      {rows.length === 0 ? (
        <div className="mt-6">
          <Empty>
            Nothing here. Conversations start when you <Link href="/review">approve a draft</Link>.
          </Empty>
        </div>
      ) : (
        <ul className="mt-6 border-t-2 border-ink">
          {rows.map((t) => (
            <li key={t.id} className={`border-b border-rule ${t.status === "needs_human" ? "needs-you" : ""}`}>
              <Link href={`/inbox/${t.id}`} className="grid gap-1 px-1 py-4 text-ink no-underline md:grid-cols-[1fr_auto] md:gap-6">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-3">
                    <span className="font-bold">{t.company.name}</span>
                    <span className="text-sm text-muted">{t.contact.name || "Team inbox"}</span>
                  </div>
                  <p className="mt-0.5 truncate text-sm text-ink-2">
                    {t.status === "needs_human" && t.handoff_reason
                      ? `Why you: ${t.handoff_reason}`
                      : t.last_message
                        ? `${t.last_message.direction === "inbound" ? "They wrote: " : "We wrote: "}${t.last_message.body}`
                        : t.subject}
                  </p>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <Bars step={t.step} out={t.status === "suppressed"} />
                  <ThreadTag status={t.status} mode={t.mode} />
                  <span className="w-16 text-right text-muted">{when(t.updated_at)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
