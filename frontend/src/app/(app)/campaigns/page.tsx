"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Empty, Loading, PageHeader, when } from "@/components/ui";
import { api, errorText, post, type Campaign } from "@/lib/api";

const STATUS: Record<string, string> = {
  running: "Running",
  done: "Done",
  stopped: "Stopped",
  failed: "Stopped by an error",
};

export default function Campaigns() {
  const { data } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api<Campaign[]>("/campaigns"),
    refetchInterval: (q) => (q.state.data?.some((c) => c.status === "running") ? 3000 : false),
  });
  const qc = useQueryClient();
  const router = useRouter();
  const anyRunning = data?.some((c) => c.status === "running");
  const rerun = useMutation({
    mutationFn: (id: number) => post<Campaign>(`/campaigns/${id}/rerun`),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      router.push(`/campaigns/${c.id}`);
    },
  });
  if (!data) return <Loading />;

  return (
    <div className="max-w-6xl">
      <PageHeader title="Campaigns" sub="Each campaign is one search for a type of brand.">
        <Link href="/campaigns/new" className="flex min-h-11 items-center bg-ink px-5 font-bold text-white no-underline">
          New campaign
        </Link>
      </PageHeader>
      {rerun.isError && <p className="mt-3 font-bold text-red">{errorText(rerun.error)}</p>}
      {data.length === 0 ? (
        <Empty>
          No campaigns yet. <Link href="/campaigns/new">Start the first one</Link>: tell the agent what kind of brand to find.
        </Empty>
      ) : (
        <div className="mt-7 overflow-x-auto border-t-2 border-ink">
          <table className="w-full min-w-[900px] border-collapse">
            <thead>
              <tr className="text-left text-[13px] text-muted">
                <th className="py-2.5 pr-3 font-medium">Campaign</th>
                <th className="w-56 px-3 font-medium">Progress</th>
                {["Found", "Good fit", "Emailed", "Replies", "Calls"].map((h) => (
                  <th key={h} className="px-3 text-right font-medium">
                    {h}
                  </th>
                ))}
                <th className="pl-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => {
                const pct = c.status === "done" ? 100 : c.progress_total ? Math.round((c.progress_done / c.progress_total) * 100) : 0;
                const s = c.settings;
                return (
                  <tr key={c.id} className="border-t border-rule align-top">
                    <td className="py-4 pr-3">
                      <Link href={`/campaigns/${c.id}`} className="text-[17px] font-bold text-ink">
                        {c.name}
                      </Link>
                      <div className="text-sm text-ink-2">
                        {[s.categories?.join(", "), s.channels?.length ? `on ${s.channels.join(", ")}` : ""].filter(Boolean).join(" ") ||
                          "Any category"}
                      </div>
                      <div className="mt-2">
                      {c.status === "running" ? (
                        <Link href={`/campaigns/${c.id}`} className="font-bold">Watch it</Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => rerun.mutate(c.id)}
                          disabled={anyRunning || rerun.isPending}
                          title={anyRunning ? "Another search is running. Wait or stop it first." : "Same settings, new brands only"}
                          className="min-h-10 border-2 border-ink px-3 text-sm font-bold disabled:cursor-not-allowed disabled:border-rule disabled:text-muted"
                        >
                          Run again
                        </button>
                      )}
                                          </div>
                    </td>
                    <td className="px-3 py-4">
                      <div className="flex justify-between text-[13px]">
                        <span className={c.status === "running" ? "bg-yellow px-1.5 font-bold" : c.status === "done" ? "font-bold" : "text-muted"}>
                          {STATUS[c.status] ?? c.status}
                        </span>
                        <span>{c.status === "running" ? c.stage : ""}</span>
                      </div>
                      <div className="mt-1.5 h-2 bg-rule-soft">
                        <div className={`h-2 ${c.status === "running" || c.status === "done" ? "bg-ink" : "bg-faint"}`} style={{ width: `${pct}%` }} />
                      </div>
                    </td>
                    {[c.stats.found, c.stats.good, c.stats.emailed, c.stats.replies].map((n, i) => (
                      <td key={i} className="px-3 py-4 text-right tabular-nums">
                        {n}
                      </td>
                    ))}
                    <td className="px-3 py-4 text-right font-bold tabular-nums">{c.stats.calls}</td>
                    <td className="py-4 pl-3 whitespace-nowrap">{when(c.created_at)}</td>

                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
