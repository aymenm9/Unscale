"use client";

import { useQuery } from "@tanstack/react-query";

import { Empty, Loading, PageHeader, when } from "@/components/ui";
import { api } from "@/lib/api";

type Row = { id: number; actor: string; action: string; entity_type: string; entity_id: number; detail: Record<string, unknown>; created_at: string };

function detailText(d: Record<string, unknown>) {
  return Object.entries(d ?? {})
    .filter(([, v]) => v !== null && v !== "" && typeof v !== "object")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v).slice(0, 120)}`)
    .join("; ");
}

export default function Log() {
  const { data } = useQuery({ queryKey: ["audit"], queryFn: () => api<Row[]>("/audit"), refetchInterval: 15000 });
  if (!data) return <Loading />;
  return (
    <div className="max-w-6xl">
      <PageHeader title="Activity log" sub="Everything the agent and the team did, newest first. The last 200 actions." />
      {data.length === 0 ? (
        <div className="mt-7"><Empty>Nothing has happened yet.</Empty></div>
      ) : (
        <div className="mt-7 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b-2 border-ink text-[13px] text-muted">
                <th className="py-2 pr-3 font-normal">When</th>
                <th className="py-2 pr-3 font-normal">Who</th>
                <th className="py-2 pr-3 font-normal">What</th>
                <th className="py-2 pr-3 font-normal">Details</th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id} className="border-b border-rule align-top">
                  <td className="py-2 pr-3 whitespace-nowrap text-muted">{when(a.created_at)}</td>
                  <td className="py-2 pr-3">{a.actor.includes("@") ? a.actor : <span className="font-bold">{a.actor}</span>}</td>
                  <td className="py-2 pr-3">{a.action.replace(/_/g, " ")} <span className="text-muted">{a.entity_type} {a.entity_id || ""}</span></td>
                  <td className="max-w-[60ch] py-2 pr-3 text-ink-2">{detailText(a.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
