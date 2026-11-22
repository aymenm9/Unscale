"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Empty, Loading, PageHeader, when } from "@/components/ui";
import { api, errorText, post } from "@/lib/api";

type Row = { email: string; reason: string; created_at: string };

export default function DoNotContact() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const { data } = useQuery({ queryKey: ["suppressions"], queryFn: () => api<Row[]>("/suppressions") });
  const add = useMutation({
    mutationFn: () => post("/suppressions", { email, reason: reason || "Added by hand" }),
    onSuccess: () => {
      setEmail("");
      setReason("");
      qc.invalidateQueries();
    },
  });
  if (!data) return <Loading />;
  const valid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || /^@[^@\s]+\.[^@\s]+$/.test(email);

  return (
    <div className="max-w-4xl">
      <PageHeader title="Do not contact" sub="Nobody on this list gets an email again, from the agent or from you. People who opt out are added on their own." />
      <form
        className="mt-7 flex flex-wrap items-end gap-3 border-y-2 border-ink py-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) add.mutate();
        }}
      >
        <label className="grid flex-[1_1_240px] gap-1 text-sm">
          <span className="font-bold">Email, or @company.com for everyone there</span>
          <input value={email} onChange={(e) => setEmail(e.target.value.trim())} className="min-h-11 border-2 border-ink px-3" placeholder="name@brand.com" />
        </label>
        <label className="grid flex-[1_1_200px] gap-1 text-sm">
          <span>Reason (optional)</span>
          <input value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-11 border-2 border-rule px-3" placeholder="Asked on a call" />
        </label>
        <Button tone="dark" type="submit" disabled={!valid || add.isPending}>Add to list</Button>
        {add.error && <p className="w-full text-red">{errorText(add.error)}</p>}
      </form>
      {data.length === 0 ? (
        <div className="mt-6"><Empty>The list is empty.</Empty></div>
      ) : (
        <ul className="mt-2">
          {data.map((s) => (
            <li key={s.email} className="grid gap-1 border-b border-rule py-3 md:grid-cols-[1fr_1fr_100px]">
              <span className="font-bold break-all">{s.email}</span>
              <span className="text-sm text-ink-2">{s.reason}</span>
              <span className="text-sm text-muted md:text-right">{when(s.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
