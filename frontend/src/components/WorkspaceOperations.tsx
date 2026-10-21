"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api";

type Member = { id: string; email: string; role: string; is_active: boolean };
type Invitation = { id: string; email: string; role: string; expires_at: string };
type Team = { members: Member[]; pending: Invitation[] };
type Billing = {
  plan: string; subscription_status: string; checkout_available: boolean;
  free_activity_limit: number; free_team_limit: number; can_manage_billing: boolean;
};

function displayError(err: unknown) {
  return err instanceof Error ? err.message : "Request unsuccessful";
}

export function TeamBilling({
  mode, token, role, onNotice, onError
}: {
  mode: "team" | "billing"; token: string; role: string;
  onNotice: (value: string) => void; onError: (value: string) => void;
}) {
  const [team, setTeam] = useState<Team | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (mode === "team") setTeam(await api<Team>("/api/team", token));
    else setBilling(await api<Billing>("/api/billing/status", token));
  }

  useEffect(() => {
    void Promise.resolve().then(refresh).catch(err => onError(displayError(err)));
    // reload when mode/token changes only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, token]);

  async function invite(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      await api("/api/team/invitations", token, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, role: inviteRole })
      });
      setEmail(""); onNotice("Invitation sent. The link expires after seven days.");
      await refresh();
    } catch (err) { onError(displayError(err)); }
    finally { setBusy(false); }
  }

  async function action(path: string, success: string) {
    setBusy(true);
    try {
      await api(path, token, { method: "POST" });
      onNotice(success); await refresh();
    } catch (err) { onError(displayError(err)); }
    finally { setBusy(false); }
  }

  async function billingRedirect(path: string) {
    setBusy(true);
    try {
      const result = await api<{ url: string }>(path, token, { method: "POST" });
      const url = new URL(result.url);
      if (url.protocol !== "https:" || !["checkout.stripe.com", "billing.stripe.com"].includes(url.hostname)) {
        throw new Error("Unexpected payment-provider redirect");
      }
      window.location.assign(url.toString());
    } catch (err) { onError(displayError(err)); setBusy(false); }
  }

  if (mode === "team") {
    return <div className="surface" style={{ display: "grid", gap: 24 }}>
      <h2>Workspace members</h2>
      <p>Invite editors who enter activity data and reviewers who validate records. Owner access is never delegated through invitation links.</p>
      <div className="table-scroll"><table><thead><tr><th>EMAIL</th><th>ROLE</th><th>ACCESS</th></tr></thead>
        <tbody>{team?.members.map(member =>
          <tr key={member.id}><td>{member.email}</td><td>{member.role}</td>
          <td>{member.is_active ? "Active" : "Revoked"} {role === "owner" && member.role !== "owner" && member.is_active &&
            <button className="btn outline" disabled={busy} onClick={() => action("/api/team/members/" + member.id + "/deactivate", "Access revoked")}>Revoke access</button>}
          </td></tr>
        )}</tbody></table></div>
      {role === "owner" && <>
        <h3>Invite a teammate</h3>
        <form onSubmit={invite} className="field-grid">
          <label>Email<input required type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="colleague@company.com" /></label>
          <label>Role<select value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
            <option value="editor">Editor — records and drafts</option>
            <option value="reviewer">Reviewer — approvals</option>
            <option value="viewer">Viewer — read only</option>
          </select></label>
          <button className="btn primary" disabled={busy}>Send invitation →</button>
        </form>
        <h3>Pending invitations</h3>
        {team?.pending.length ? team.pending.map(inv =>
          <div className="hint-row" key={inv.id}><span>{inv.email} · {inv.role} · expires {new Date(inv.expires_at).toLocaleDateString("en-GB")}</span>
          <button className="btn outline" disabled={busy} onClick={() => action("/api/team/invitations/" + inv.id + "/revoke", "Invitation revoked")}>Revoke invitation</button></div>
        ) : <p>No pending invitations.</p>}
      </>}
      <button className="btn outline" onClick={() => void refresh()} disabled={busy}>Refresh team</button>
    </div>;
  }

  return <div className="surface" style={{ maxWidth: 820 }}>
    <div className="label-soft">SUBSCRIPTION</div>
    <h2 style={{ marginTop: 12 }}>Plan: {billing?.plan === "pro" ? "RegTech Pro" : "Free pilot"}</h2>
    <p>Status: <strong>{billing?.subscription_status ?? "Loading…"}</strong></p>
    <p>Free plan supports {billing?.free_activity_limit ?? 25} non-voided activity records and {billing?.free_team_limit ?? 3} team members. Subscriptions become active only when a verified payment-provider webhook confirms payment status.</p>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
      {billing?.can_manage_billing && billing.checkout_available && billing.plan !== "pro" &&
        <button className="btn primary" onClick={() => billingRedirect("/api/billing/checkout")} disabled={busy}>Upgrade securely with Stripe →</button>}
      {billing?.can_manage_billing && billing.checkout_available &&
        <button className="btn outline" onClick={() => billingRedirect("/api/billing/portal")} disabled={busy}>Manage subscription</button>}
      <button className="btn outline" onClick={() => void refresh()} disabled={busy}>Refresh billing status</button>
    </div>
    {!billing?.checkout_available && <p>Online payment setup is not yet connected. No card details are collected by RegTech.</p>}
    <p style={{ marginTop: 24 }}>Charges and cancellation terms must be configured and reviewed before offering live subscriptions. The checkout flow is disabled until the operator supplies Stripe keys and an approved price.</p>
  </div>;
}

export function CsvImporter({
  token, onImported, onError
}: { token: string; onImported: (message: string) => void; onError: (error: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const header = "description,supplier,activity_date,factor_id,quantity,unit,scope,evidence_reference\n";
  function template() {
    const object = URL.createObjectURL(new Blob([header], { type: "text/csv;charset=utf-8" }));
    const el = document.createElement("a");
    el.href = object; el.download = "regtech-activity-template.csv"; el.click();
    setTimeout(() => URL.revokeObjectURL(object), 1000);
  }
  async function upload(event: FormEvent) {
    event.preventDefault(); if (!file) return;
    setBusy(true);
    try {
      const data = new FormData(); data.append("file", file);
      const result = await api<{ created: number }>("/api/activities/import-csv", token, { method: "POST", body: data });
      setFile(null); onImported(result.created + " draft activities imported. Review each before approving.");
    } catch (err) { onError(displayError(err)); }
    finally { setBusy(false); }
  }
  return <div className="surface" style={{ marginTop: 22 }}>
    <div className="panel-heading"><h2>Bulk import</h2><span className="mini-pill">CSV · UP TO 100 ROWS</span></div>
    <p>Use verified physical quantities and exact factor units. Invalid rows reject the entire file; records are saved as drafts only.</p>
    <button className="btn outline" type="button" onClick={template}>↓ Download CSV template</button>
    <form onSubmit={upload} style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 18, flexWrap: "wrap" }}>
      <input aria-label="Choose CSV file" type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] || null)} style={{ maxWidth: 340 }} />
      <button className="btn primary" disabled={busy || !file}>{busy ? "Importing…" : "Import drafts →"}</button>
    </form>
  </div>;
}
