"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Loading, PageHeader, Progress, Score, Stats, Tabs, Track } from "@/components/ui";
import { api, errorText, post, type Campaign, type CampaignDetail } from "@/lib/api";

const STAGE_LABEL: Record<string, string> = {
  code_check: "Store check",
  quick_filter: "Quick filter",
  research: "Research",
  qualifier: "Scoring",
  contact: "Finding a person",
  writer: "Writing",
};
const STEPS = ["search", "check", "filter", "research", "qualify", "contacts", "write"];
const STEP_LABEL: Record<string, string> = {
  search: "Searching for brands",
  check: "Checking each store is in the US",
  filter: "Quick filter",
  research: "Reading websites and news for proof",
  qualify: "Scoring each company",
  contacts: "Finding the right person",
  write: "Writing first emails",
};

type Tab = "all" | "good" | "maybe" | "poor" | "rejected";

export default function CampaignPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("all");
  const { data } = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => api<CampaignDetail>(`/campaigns/${id}`),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 2500 : false),
  });
  const stop = useMutation({
    mutationFn: () => post(`/campaigns/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaign", id] }),
  });
  const router = useRouter();
  const rerun = useMutation({
    mutationFn: () => post<Campaign>(`/campaigns/${id}/rerun`),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      router.push(`/campaigns/${c.id}`);
    },
  });
  if (!data) return <Loading />;

  const s = data.settings;
  const running = data.status === "running";
  const stageIndex = STEPS.indexOf(data.stage);
  const companies = data.companies.filter((c) => tab === "all" || c.verdict === tab);
  const counts = { good: data.stats.good, maybe: data.stats.maybe, poor: data.stats.poor };

  return (
    <div className="max-w-7xl">
      <PageHeader
        title={data.name}
        back={{ href: "/campaigns", label: "campaigns" }}
        sub={
          <>
            {s.categories?.join(", ") || "Any category"}. {s.channels?.join(" and ")}. ${s.revenue_min}M to ${s.revenue_max}M, {s.staff_min} to {s.staff_max} people, {s.location ?? "anywhere in the US"}.
          </>
        }
      >
        {running && (
          <Button onClick={() => stop.mutate()} disabled={stop.isPending}>
            Stop
          </Button>
        )}
        {!running && (
          <Button tone="yellow" onClick={() => rerun.mutate()} disabled={rerun.isPending}>
            {rerun.isPending ? "Starting…" : "Run this search again"}
          </Button>
        )}
        <Link href={`/companies?campaign=${data.id}`} className="flex min-h-11 items-center border-2 border-ink px-5 text-ink no-underline">
          See its companies
        </Link>
        {data.stats.drafts > 0 && (
          <Link href="/review" className="flex min-h-11 items-center bg-ink px-5 font-bold text-white no-underline">
            Review {data.stats.drafts} {data.stats.drafts === 1 ? "draft" : "drafts"}
          </Link>
        )}
      </PageHeader>
      {rerun.isError && <p className="mt-3 font-bold text-red">{errorText(rerun.error)}</p>}

      <div className="mt-6 flex max-w-4xl flex-wrap gap-8">
        <div className="min-w-[280px] flex-1">
          <Progress
            done={data.status === "done" ? 1 : data.progress_done}
            total={data.status === "done" ? 1 : data.progress_total}
            label={running ? STEP_LABEL[data.stage] ?? "Starting" : data.status === "done" ? "Finished" : "Stopped"}
            note={data.message}
          />
        </div>
        {running && (
          <ol className="grid list-decimal gap-1 pl-5 text-sm">
            {STEPS.map((st, i) => (
              <li key={st} className={i === stageIndex ? "font-bold" : i < stageIndex ? "" : "text-faint"}>
                {STEP_LABEL[st]}
              </li>
            ))}
          </ol>
        )}
      </div>

      <Stats
        items={[
          { n: data.stats.found, label: "found" },
          { n: data.stats.good, label: "good fit" },
          { n: data.stats.maybe, label: "maybe" },
          { n: data.rejections.length, label: "not chosen" },
          { n: data.stats.drafts, label: "drafts ready" },
        ]}
      />

      <div className="mt-7">
        <Tabs<Tab>
          value={tab}
          onChange={setTab}
          items={[
            { key: "all", label: `All ${data.companies.length}` },
            { key: "good", label: `Good fit ${counts.good}` },
            { key: "maybe", label: `Maybe ${counts.maybe}` },
            { key: "poor", label: `Not a fit ${counts.poor}` },
            { key: "rejected", label: `Not chosen ${data.rejections.length}` },
          ]}
        />
      </div>

      {tab === "rejected" ? (
        <div className="mt-3.5 overflow-x-auto border-t-2 border-ink">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr className="text-left text-[13px] text-muted">
                <th className="py-2.5 pr-3 font-medium">Company</th>
                <th className="px-3 font-medium">Stopped at</th>
                <th className="pl-3 font-medium">Why</th>
              </tr>
            </thead>
            <tbody>
              {data.rejections.map((r) => (
                <tr key={r.id} className="border-t border-rule align-top">
                  <td className="py-3.5 pr-3">
                    <div className="font-bold">
                      {r.company_id ? <Link href={`/companies/${r.company_id}`} className="text-ink">{r.name}</Link> : r.name}
                    </div>
                    <div className="text-[13px] text-muted">{r.domain}</div>
                  </td>
                  <td className="px-3 py-3.5 whitespace-nowrap">{STAGE_LABEL[r.stage] ?? r.stage}</td>
                  <td className="py-3.5 pl-3 text-sm">{r.reason}</td>
                </tr>
              ))}
              {data.rejections.length === 0 && (
                <tr><td colSpan={3} className="py-6 text-ink-2">Nothing dropped yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-3.5 overflow-x-auto border-t-2 border-ink">
          <table className="w-full min-w-[1000px] border-collapse">
            <thead>
              <tr className="text-left text-[13px] text-muted">
                <th className="py-2.5 pr-3 font-medium">Company</th>
                <th className="px-3 font-medium">Sells</th>
                <th className="px-3 font-medium">Revenue</th>
                <th className="px-3 text-right font-medium">Fit</th>
                <th className="px-3 font-medium">Why</th>
                <th className="w-56 px-3 font-medium">Where it is</th>
                <th className="pl-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c.id} className={`border-t border-rule align-top ${c.needs_you ? "bg-yellow-soft" : ""} ${c.verdict === "poor" ? "text-muted" : ""}`}>
                  <td className="py-3.5 pr-3">
                    <Link href={`/companies/${c.id}`} className="font-bold text-ink">{c.name}</Link>
                    <div className="text-[13px] text-muted">{c.location || c.domain}</div>
                  </td>
                  <td className="px-3 py-3.5 text-sm">{c.channels.join(", ") || c.platform}</td>
                  <td className="px-3 py-3.5 text-sm whitespace-nowrap">
                    {c.revenue_band || "Unknown"}
                    {c.revenue_confidence && <div className="text-[13px] text-muted">{c.revenue_confidence} confidence</div>}
                  </td>
                  <td className="px-3 py-3.5 text-right"><Score value={c.score} verdict={c.verdict} /></td>
                  <td className="max-w-[300px] px-3 py-3.5 text-sm">
                    {c.why}
                    <div className="text-[13px] text-muted">{c.evidence_count} sources</div>
                  </td>
                  <td className="px-3 py-3.5"><Track step={c.step} small labels={false} out={c.verdict === "poor"} /></td>
                  <td className="py-3.5 pl-3 text-sm font-bold whitespace-nowrap">
                    {c.needs_you && c.thread_id ? <Link href={`/inbox/${c.thread_id}`}>Reply now</Link>
                      : c.draft_id ? <Link href={`/review#draft-${c.draft_id}`}>Review draft</Link>
                      : c.thread_id ? <Link href={`/inbox/${c.thread_id}`}>Read thread</Link>
                      : <Link href={`/companies/${c.id}`}>Read report</Link>}
                  </td>
                </tr>
              ))}
              {companies.length === 0 && (
                <tr><td colSpan={7} className="py-6 text-ink-2">{running ? "Companies appear here as the agent researches them." : "No companies in this group."}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
