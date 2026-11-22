"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui";
import { api, errorText } from "@/lib/api";

type TestMode = { on: boolean; email: string; demo_inbox: string };

/** Test mode: every email the agent sends goes to the person's own inbox. */
export function TestModePanel({ firstThreadId }: { firstThreadId?: number }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["test-mode"], queryFn: () => api<TestMode>("/test-mode") });
  const [email, setEmail] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (value: string) => api<TestMode>("/test-mode", { method: "PUT", body: { email: value } }),
    onSuccess: (d) => {
      qc.setQueryData(["test-mode"], d);
      setEmail(null);
    },
  });
  if (!data) return null;
  const value = email ?? data.email;

  return (
    <section className={`border-t-4 p-4 ${data.on ? "border-yellow bg-yellow/15" : "border-ink bg-rule-soft"}`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="semi-wide text-[18px] font-extrabold">Test mode</h2>
        <span className={`px-2 text-[13px] font-bold ${data.on ? "bg-ink text-yellow" : "border-2 border-ink"}`}>{data.on ? "On" : "Off"}</span>
      </div>
      <p className="mt-1 text-sm text-ink-2">
        {data.on ? (
          <>
            Every email goes to <b>{data.email}</b>. No company is contacted.
          </>
        ) : (
          <>Emails now go to a test inbox you can&apos;t read. Add your email to receive them yourself.</>
        )}
      </p>
      <form
        className="mt-3 flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(value);
        }}
      >
        <input
          type="email"
          value={value}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-label="Your email for test mode"
          className="min-h-11 border-2 border-ink bg-white px-3"
        />
        <div className="flex gap-2">
          <Button tone="dark" type="submit" disabled={save.isPending || !value.trim() || value === data.email}>
            {data.on ? "Change email" : "Turn on"}
          </Button>
          {data.on && (
            <Button type="button" onClick={() => save.mutate("")} disabled={save.isPending}>
              Turn off
            </Button>
          )}
        </div>
      </form>
      {save.isError && <p className="mt-2 text-sm font-bold text-red">{errorText(save.error)}</p>}
      <p className="mt-3 text-[13px] text-muted">
        The free email sender only delivers to the address you signed up to Resend with.
      </p>
      <p className="mt-2 text-sm">
        <b>See what the agent does with a reply:</b>{" "}
        {firstThreadId ? (
          <Link href={`/inbox/${firstThreadId}#test-reply`}>reply as the prospect</Link>
        ) : (
          "approve a first email, then open its conversation"
        )}
        . Replies sent from your own inbox reach the app only when it runs online.
      </p>
    </section>
  );
}

const STEPS = [
  { title: "Start a campaign", text: "Describe the brands to find. The agent searches, checks each store and scores it.", href: "/campaigns/new", link: "New campaign" },
  { title: "Approve first emails", text: "Read each draft with its sources. Edit, approve or reject. Nothing is sent before you approve.", href: "/review", link: "Approve drafts" },
  { title: "Watch conversations", text: "The agent answers replies on its own. Yellow rows need you: it explains why.", href: "/inbox", link: "Conversations" },
  { title: "Take a call", text: "When a prospect says yes, the agent books a call and it shows up here.", href: "/calls", link: "Calls" },
];

/** Short how-to for a first-time user. */
export function HowTo() {
  return (
    <details open className="border-t-2 border-ink pt-3">
      <summary className="semi-wide cursor-pointer text-[18px] font-extrabold">How to use the app</summary>
      <ol className="mt-3 grid gap-3">
        {STEPS.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[28px_1fr] gap-2">
            <span className="flex size-7 items-center justify-center bg-yellow text-sm font-extrabold">{i + 1}</span>
            <span>
              <span className="block font-bold">{s.title}</span>
              <span className="block text-sm text-ink-2">{s.text}</span>
              <Link href={s.href} className="text-sm font-bold">
                {s.link}
              </Link>
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[13px] text-muted">
        The agent never quotes prices, never says something it can&apos;t back with a source, and stops for good when someone says stop.
      </p>
    </details>
  );
}
