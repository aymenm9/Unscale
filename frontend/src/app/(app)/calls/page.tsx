"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Empty, Loading, PageHeader } from "@/components/ui";
import { api, type CompanyRow } from "@/lib/api";

type Meeting = { id: number; thread_id: number; start_at: string; label: string; company: CompanyRow };

function List({ items }: { items: Meeting[] }) {
  return (
    <ul className="border-t-2 border-ink">
      {items.map((m) => (
        <li key={m.id} className="grid gap-1 border-b border-rule py-4 md:grid-cols-[220px_1fr_auto] md:items-baseline md:gap-6">
          <span className="semi-wide font-extrabold">{m.label}</span>
          <span>
            <Link href={`/companies/${m.company.id}`} className="font-bold text-ink">{m.company.name}</Link>
            <span className="text-sm text-muted"> {m.company.domain}</span>
          </span>
          <Link href={`/inbox/${m.thread_id}`} className="text-sm">Call prep and thread</Link>
        </li>
      ))}
    </ul>
  );
}

export default function Calls() {
  const { data } = useQuery({ queryKey: ["meetings"], queryFn: () => api<Meeting[]>("/meetings") });
  const [now] = useState(() => Date.now());
  if (!data) return <Loading />;
  const upcoming = data.filter((m) => new Date(m.start_at.endsWith("Z") ? m.start_at : `${m.start_at}Z`).getTime() >= now);
  const past = data.filter((m) => !upcoming.includes(m));

  return (
    <div className="max-w-5xl">
      <PageHeader title="Calls" sub="Calls the agent booked. Open one to read the call prep before you join." />
      <div className="mt-7">
        {upcoming.length ? <List items={upcoming} /> : <Empty>No calls booked yet. The agent books one when a prospect agrees to a time.</Empty>}
      </div>
      {past.length > 0 && (
        <section className="mt-10">
          <h2 className="semi-wide mb-3 text-xl font-extrabold">Past calls</h2>
          <List items={past} />
        </section>
      )}
    </div>
  );
}
