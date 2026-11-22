"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Empty, Loading, PageHeader, Score, Tabs } from "@/components/ui";
import { api, type Campaign, type CompanyRow } from "@/lib/api";

type Filter = "all" | "good" | "maybe" | "poor";

export default function Companies() {
  return (
    <Suspense fallback={<Loading />}>
      <CompaniesList />
    </Suspense>
  );
}

function CompaniesList() {
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const router = useRouter();
  const campaign = useSearchParams().get("campaign") ?? "";
  const setCampaign = (v: string) => router.replace(v ? `/companies?campaign=${v}` : "/companies");
  const { data } = useQuery({ queryKey: ["companies"], queryFn: () => api<CompanyRow[]>("/companies") });
  const { data: campaigns = [] } = useQuery({ queryKey: ["campaigns"], queryFn: () => api<Campaign[]>("/campaigns") });
  if (!data) return <Loading />;
  const campaignName = (id: number | null) => campaigns.find((c) => c.id === id)?.name;
  const inCampaign = data.filter((c) => !campaign || String(c.campaign_id) === campaign);
  const rows = inCampaign.filter(
    (c) => (filter === "all" || c.verdict === filter) && `${c.name} ${c.domain}`.toLowerCase().includes(q.toLowerCase()),
  );
  const count = (v: Filter) => inCampaign.filter((c) => v === "all" || c.verdict === v).length;

  return (
    <div className="max-w-6xl">
      <PageHeader title="Companies" sub="Every company the agent researched. Pick a campaign to see only its companies. Best fit first." />
      <div className="mt-7 flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={filter}
          onChange={setFilter}
          items={[
            { key: "all", label: `All ${count("all")}` },
            { key: "good", label: `Good fit ${count("good")}` },
            { key: "maybe", label: `Maybe ${count("maybe")}` },
            { key: "poor", label: `Poor fit ${count("poor")}` },
          ]}
        />
        <div className="flex w-full flex-wrap gap-3 sm:w-auto">
        <select
          value={campaign}
          onChange={(e) => setCampaign(e.target.value)}
          aria-label="Filter by campaign"
          className="min-h-11 w-full border-2 border-rule bg-white px-3 sm:w-56"
        >
          <option value="">All campaigns</option>
          {campaigns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} (#{c.id})
            </option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by name or website"
          aria-label="Search companies"
          className="min-h-11 w-full border-2 border-rule px-3 sm:w-64"
        />
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="mt-6">
          <Empty>No companies match. Try another filter, or start a campaign.</Empty>
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="border-b-2 border-ink text-[13px] text-muted">
                <th className="py-2 pr-3 font-normal">Fit</th>
                <th className="py-2 pr-3 font-normal">Company</th>
                <th className="py-2 pr-3 font-normal">Why</th>
                <th className="py-2 pr-3 font-normal">Revenue</th>
                <th className="py-2 pr-3 font-normal">Sources</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-b border-rule align-top">
                  <td className="py-3 pr-3">
                    <Score value={c.score} verdict={c.verdict} />
                  </td>
                  <td className="py-3 pr-3">
                    <Link href={`/companies/${c.id}`} className="font-bold text-ink">
                      {c.name}
                    </Link>
                    <div className="text-[13px] text-muted">
                      {c.domain}
                      {c.location ? `, ${c.location}` : ""}
                    </div>
                    {!campaign && campaignName(c.campaign_id) && (
                      <Link href={`/campaigns/${c.campaign_id}`} className="text-[13px] text-ink-2">
                        {campaignName(c.campaign_id)}
                      </Link>
                    )}
                  </td>
                  <td className="max-w-[46ch] py-3 pr-3 text-sm text-ink-2">{c.why || "—"}</td>
                  <td className="py-3 pr-3 text-sm">
                    {c.revenue_band || "—"}
                    {c.revenue_confidence === "low" && <div className="text-[13px] text-muted">a guess</div>}
                  </td>
                  <td className="py-3 pr-3 text-sm tabular-nums">{c.evidence_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
