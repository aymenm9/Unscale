"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, PageHeader } from "@/components/ui";
import { errorText, post, type Campaign } from "@/lib/api";

const CATEGORIES = ["Gifts", "Home goods", "Candles", "Apparel", "Beauty and skincare", "Food and drink", "Supplements", "Pet", "Outdoor", "Baby and kids"];
const CHANNELS = ["Shopify", "Amazon", "Wholesale", "Etsy", "TikTok Shop", "Walmart"];
const SIGNALS = ["Raised money recently", "Hiring ops or finance", "Added a new sales channel", "Fast product growth", "Ships abroad", "Uses a 3PL warehouse"];
const ROLES = [
  { key: "founder", label: "Founder" },
  { key: "ops", label: "COO or head of ops" },
  { key: "finance", label: "Finance lead" },
];
const VOICES = [
  { key: "auto", name: "Pick by role", sample: "Founder gets Peer founder, COO gets Numbers-first, finance gets Finance peer." },
  { key: "peer_founder", name: "Peer founder", sample: "“Saw you launched wholesale in October. That usually means a third set of payouts to match.”" },
  { key: "numbers_operator", name: "Numbers-first operator", sample: "“Three channels, three payout schedules, one month-end close.”" },
  { key: "finance_peer", name: "Finance peer", sample: "“Amazon reimbursements are easy to miss once you pass 1,000 orders a month.”" },
];

function Chips({ all, value, onChange }: { all: string[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {all.map((label) => {
        const on = value.includes(label);
        return (
          <button
            type="button"
            key={label}
            aria-pressed={on}
            onClick={() => onChange(on ? value.filter((x) => x !== label) : [...value, label])}
            className={`min-h-10 border-2 px-3.5 ${on ? "border-ink bg-ink font-bold text-white" : "border-rule bg-white"}`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

function Field({ label, hint, children, first = false }: { label: string; hint?: string; children: React.ReactNode; first?: boolean }) {
  return (
    <div className={`mt-6 pt-5 ${first ? "border-t-2 border-ink" : "border-t border-rule"}`}>
      <span className="block text-base font-bold">{label}</span>
      {hint && <span className="block text-[13px] text-muted">{hint}</span>}
      {children}
    </div>
  );
}

const select = "min-h-11 border-2 border-ink bg-white px-2";

export default function NewCampaign() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("Holiday gift brands");
  const [categories, setCategories] = useState<string[]>(["Gifts", "Home goods", "Candles"]);
  const [channels, setChannels] = useState<string[]>(["Shopify", "Amazon"]);
  const [revenue, setRevenue] = useState<[number, number]>([1, 10]);
  const [staff, setStaff] = useState<[number, number]>([5, 50]);
  const [signals, setSignals] = useState<string[]>(["Raised money recently", "Hiring ops or finance"]);
  const [roles, setRoles] = useState<string[]>(["founder", "ops", "finance"]);
  const [voice, setVoice] = useState("auto");
  const [target, setTarget] = useState(30);

  const start = useMutation({
    mutationFn: () =>
      post<Campaign>("/campaigns", {
        name,
        categories,
        channels,
        revenue_min: revenue[0],
        revenue_max: revenue[1],
        staff_min: staff[0],
        staff_max: staff[1],
        location: "Anywhere in the US",
        signals,
        roles,
        voice,
        target,
      }),
    onSuccess: (c) => {
      qc.invalidateQueries();
      router.push(`/campaigns/${c.id}`);
    },
  });

  const roleNames = ROLES.filter((r) => roles.includes(r.key)).map((r) => r.label.toLowerCase());
  const voiceName = VOICES.find((v) => v.key === voice)?.name.toLowerCase();

  return (
    <div className="flex max-w-6xl flex-wrap gap-10">
      <form
        className="min-w-0 max-w-3xl flex-[1_1_520px]"
        onSubmit={(e) => {
          e.preventDefault();
          start.mutate();
        }}
      >
        <PageHeader
          title="New campaign"
          back={{ href: "/campaigns", label: "campaigns" }}
          sub="Tell the agent who to look for. It finds real companies, checks each one with sources, and writes first emails. Nothing is sent until you approve it."
        />
        <Field label="Campaign name" first>
          <input value={name} onChange={(e) => setName(e.target.value)} required aria-label="Campaign name" className="mt-2 min-h-11 w-full border-2 border-ink px-3" />
        </Field>
        <Field label="What do they sell?" hint="Pick one or more categories.">
          <Chips all={CATEGORIES} value={categories} onChange={setCategories} />
        </Field>
        <Field label="Where do they sell?" hint="Brands selling in more than one place have the messiest books.">
          <Chips all={CHANNELS} value={channels} onChange={setChannels} />
        </Field>
        <Field label="Size">
          <div className="mt-2 flex flex-wrap gap-6">
            <label className="flex items-center gap-2">
              <span className="text-sm">Revenue</span>
              <select className={select} value={revenue[0]} onChange={(e) => setRevenue([+e.target.value, revenue[1]])} aria-label="Minimum revenue">
                {[1, 2, 3, 5].map((n) => <option key={n} value={n}>${n}M</option>)}
              </select>
              to
              <select className={select} value={revenue[1]} onChange={(e) => setRevenue([revenue[0], +e.target.value])} aria-label="Maximum revenue">
                {[5, 10, 15, 20].map((n) => <option key={n} value={n}>${n}M</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-sm">Team</span>
              <select className={select} value={staff[0]} onChange={(e) => setStaff([+e.target.value, staff[1]])} aria-label="Minimum staff">
                {[1, 5, 10].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              to
              <select className={select} value={staff[1]} onChange={(e) => setStaff([staff[0], +e.target.value])} aria-label="Maximum staff">
                {[20, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              people
            </label>
            <span className="self-center text-sm text-muted">Anywhere in the US</span>
          </div>
        </Field>
        <Field label="Good signs to look for" hint="Companies with these get a higher fit score.">
          <Chips all={SIGNALS} value={signals} onChange={setSignals} />
        </Field>
        <Field label="Who should we email?">
          <div className="mt-2 flex flex-wrap gap-2">
            {ROLES.map((r) => {
              const on = roles.includes(r.key);
              return (
                <button
                  type="button"
                  key={r.key}
                  aria-pressed={on}
                  onClick={() => setRoles(on ? roles.filter((x) => x !== r.key) : [...roles, r.key])}
                  className={`min-h-10 border-2 px-3.5 ${on ? "border-ink bg-ink font-bold text-white" : "border-rule bg-white"}`}
                >
                  {r.label}
                </button>
              );
            })}
          </div>
        </Field>
        <Field label="Email voice">
          <div className="mt-2">
            {VOICES.map((v) => (
              <label key={v.key} className={`flex cursor-pointer items-start gap-3 border-b border-rule-soft px-3.5 py-3 ${voice === v.key ? "needs-you" : ""}`}>
                <input type="radio" name="voice" checked={voice === v.key} onChange={() => setVoice(v.key)} className="mt-1 size-[18px] accent-black" />
                <span>
                  <span className="block font-bold">{v.name}</span>
                  <span className="block text-sm text-ink-2">{v.sample}</span>
                </span>
              </label>
            ))}
          </div>
        </Field>
        <Field label="How many companies?">
          <div className="mt-2 flex flex-wrap items-center gap-6">
            <select className={select} value={target} onChange={(e) => setTarget(+e.target.value)} aria-label="Number of companies">
              {[5, 10, 20, 30, 40, 50].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <p className="flex-1 text-sm">Every first email waits in Approve drafts. Prices are never quoted. Anyone who says stop is never contacted again.</p>
          </div>
        </Field>
      </form>

      <aside className="min-w-[260px] flex-[0_1_300px] self-start bg-ink p-7 text-white md:sticky md:top-8">
        <h2 className="semi-wide text-[22px] font-extrabold text-yellow">The agent will look for</h2>
        <p className="mt-2.5 text-[17px] leading-snug">
          US brands selling <b>{categories.join(", ").toLowerCase() || "anything"}</b>
          {channels.length ? (
            <>
              {" "}on <b>{channels.join(" and ")}</b>
            </>
          ) : null}
          , with ${revenue[0]}M to ${revenue[1]}M revenue and {staff[0]} to {staff[1]} people.
          {signals.length ? ` Extra points for: ${signals.join(", ").toLowerCase()}.` : ""}
        </p>
        <p className="mt-3.5">
          It will email the {roleNames.join(", ") || "founder"} in the {voiceName} voice.
        </p>
        <dl className="mt-5 grid gap-2.5 border-t border-[#444] pt-4 text-sm">
          <div className="flex justify-between"><dt className="text-[#BDBDBD]">Companies</dt><dd>{target}</dd></div>
          <div className="flex justify-between"><dt className="text-[#BDBDBD]">Time to finish</dt><dd>About {Math.round(target * 1.5)} min</dd></div>
          <div className="flex justify-between"><dt className="text-[#BDBDBD]">Search credits</dt><dd>Up to 300 of 1,000</dd></div>
        </dl>
        {start.error && <p className="mt-4 text-yellow" role="alert">{errorText(start.error)}</p>}
        <Button tone="yellow" className="mt-6 w-full text-base" disabled={start.isPending || !name || !categories.length} onClick={() => start.mutate()}>
          {start.isPending ? "Starting…" : "Start campaign"}
        </Button>
      </aside>
    </div>
  );
}
