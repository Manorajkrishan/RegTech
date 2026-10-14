"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, download, type Activity, type FactorCatalog, type InvoiceHints, type Summary } from "@/lib/api";

type UserInfo = { email: string; role: string; organisation: string };
type ActivityForm = {
  description: string; supplier: string; activity_date: string; factor_id: string;
  quantity: string; unit: string; scope: string; evidence_reference: string;
};
const blank = (): ActivityForm => ({
  description: "", supplier: "", activity_date: "", factor_id: "",
  quantity: "", unit: "", scope: "", evidence_reference: ""
});
const number = (value: number) => new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(value);

export default function Home() {
  // Access tokens deliberately remain in memory only; there is no localStorage persistence.
  const [token, setToken] = useState("");
  const [registerMode, setRegisterMode] = useState(false);
  const [identity, setIdentity] = useState({ organisation: "", email: "", password: "" });
  const [user, setUser] = useState<UserInfo | null>(null);
  const [catalog, setCatalog] = useState<FactorCatalog | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [section, setSection] = useState<"overview" | "activities" | "documents">("overview");
  const [form, setForm] = useState<ActivityForm>(blank());
  const [editingId, setEditingId] = useState("");
  const [doc, setDoc] = useState<File | null>(null);
  const [hints, setHints] = useState<InvoiceHints | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh(auth: string) {
    const [me, factors, rows, report] = await Promise.all([
      api<UserInfo>("/api/me", auth),
      api<FactorCatalog>("/api/factors", auth),
      api<Activity[]>("/api/activities", auth),
      api<Summary>("/api/reports/summary", auth)
    ]);
    setUser(me); setCatalog(factors); setActivities(rows); setSummary(report);
  }

  useEffect(() => {
    if (!token) return;
    refresh(token).catch((err) => {
      setError(err.message);
      if (/auth|401/i.test(err.message)) setToken("");
    });
  }, [token]);

  function logout() {
    setToken(""); setUser(null); setCatalog(null); setSummary(null); setActivities([]);
    setHints(null); setIdentity({ organisation: "", email: "", password: "" });
    setError(""); setNotice("");
  }

  async function submitAuth(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    const path = registerMode ? "/api/auth/register" : "/api/auth/login";
    try {
      const response = await api<{ access_token: string }>(path, "", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(registerMode ? identity : { email: identity.email, password: identity.password })
      });
      setIdentity((prev) => ({ ...prev, password: "" }));
      setToken(response.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally { setBusy(false); }
  }

  function chooseFactor(value: string) {
    const factor = catalog?.factors.find((item) => item.id === value);
    setForm((prev) => ({ ...prev, factor_id: value, unit: factor?.unit || "" }));
  }

  async function submitActivity(event: FormEvent) {
    event.preventDefault(); setError(""); setNotice(""); setBusy(true);
    try {
      if (!form.factor_id || !form.scope || !form.quantity) throw new Error("Select a factor, activity quantity and scope.");
      const payload = { ...form, quantity: Number(form.quantity) };
      await api(editingId ? "/api/activities/" + editingId : "/api/activities",
        token, { method: editingId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setNotice(editingId ? "Draft updated. Review before approval." : "Saved as draft; approval is required before reporting.");
      setForm(blank()); setEditingId(""); await refresh(token);
      setSection("activities");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save activity"); }
    finally { setBusy(false); }
  }

  async function statusChange(id: string, action: "approve" | "void") {
    setBusy(true); setError(""); setNotice("");
    try {
      await api("/api/activities/" + id + "/" + action, token, { method: "PATCH" });
      setNotice(action === "approve" ? "Record approved and included in your draft inventory." : "Record voided and excluded from reporting.");
      await refresh(token);
    } catch (err) { setError(err instanceof Error ? err.message : "Update failed"); }
    finally { setBusy(false); }
  }

  async function processDocument(event: FormEvent) {
    event.preventDefault(); if (!doc) return;
    setBusy(true); setError(""); setHints(null);
    try {
      const body = new FormData(); body.set("file", doc);
      setHints(await api<InvoiceHints>("/api/invoices/extract", token, { method: "POST", body }));
    } catch (err) { setError(err instanceof Error ? err.message : "OCR failed"); }
    finally { setBusy(false); }
  }

  function applyDocumentHint(hint: { quantity: number; unit: string; evidence: string }) {
    setForm({ ...blank(), supplier: hints?.extracted.supplier || "",
      activity_date: hints?.extracted.date || "", quantity: String(hint.quantity),
      unit: hint.unit, evidence_reference: "Invoice checked: " + hint.evidence });
    setSection("activities"); setNotice("Document data prefilled. Choose a factor, scope and description; verify against the original.");
  }

  async function exportReport(path: string, name: string) {
    setBusy(true); setError("");
    try { await download(token, path, name); }
    catch (err) { setError(err instanceof Error ? err.message : "Export failed"); }
    finally { setBusy(false); }
  }

  const supported = catalog?.factors.filter((factor) => factor.supported) || [];
  const drafts = activities.filter((activity) => activity.status === "draft").length;

  if (!token) {
    return <main className="auth-screen">
      <div className="auth-shell">
        <div className="auth-story">
          <div className="brand-mark">R<span>.</span></div>
          <div className="eyebrow">CARBON INTELLIGENCE / WORKSPACE</div>
          <h1>Measure what matters.<br /><em>Prove what you report.</em></h1>
          <p>An activity-based carbon workspace for growing organisations. Review every number, keep evidence, and export transparent draft inventories.</p>
          <div className="trust-line">Activity first · Source-linked factors · Human-reviewed data</div>
        </div>
        <form className="auth-card" onSubmit={submitAuth}>
          <span className="label-soft">WORKSPACE ACCESS</span>
          <h2>{registerMode ? "Create a workspace" : "Welcome back"}</h2>
          <p>{registerMode ? "Start an isolated company workspace." : "Sign in to manage your organisation’s carbon inventory."}</p>
          {registerMode && <label>Organisation name<input required minLength={2} maxLength={150} value={identity.organisation} onChange={(e) => setIdentity({ ...identity, organisation: e.target.value })} placeholder="Example Ltd" /></label>}
          <label>Work email<input required type="email" autoComplete="username" value={identity.email} onChange={(e) => setIdentity({ ...identity, email: e.target.value })} placeholder="you@company.com" /></label>
          <label>Password<input required type="password" minLength={registerMode ? 12 : undefined} autoComplete={registerMode ? "new-password" : "current-password"} value={identity.password} onChange={(e) => setIdentity({ ...identity, password: e.target.value })} placeholder={registerMode ? "12+ characters" : "Your password"} /></label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn primary full" disabled={busy}>{busy ? "Working…" : registerMode ? "Create workspace" : "Sign in"} <span>→</span></button>
          <button className="text-button" type="button" onClick={() => { setRegisterMode(!registerMode); setError(""); }}>{registerMode ? "Already have an account? Sign in" : "New to RegTech? Create a workspace"}</button>
          <div className="tiny-note">Early access pilot. No regulatory certification implied. Sessions expire; password recovery is not yet available.</div>
        </form>
      </div>
    </main>;
  }

  return <div className="app-shell">
    <aside className="side">
      <div className="side-brand"><span className="brand-mini">R.</span><span>REGTECH<small>CARBON WORKSPACE</small></span></div>
      <div className="nav-group-title">WORKSPACE</div>
      <nav aria-label="Primary">
        <button className={section === "overview" ? "nav active" : "nav"} onClick={() => setSection("overview")}><span>◫</span> Overview</button>
        <button className={section === "activities" ? "nav active" : "nav"} onClick={() => setSection("activities")}><span>▤</span> Activity ledger <small>{drafts}</small></button>
        <button className={section === "documents" ? "nav active" : "nav"} onClick={() => setSection("documents")}><span>↥</span> Document review</button>
      </nav>
      <div className="side-bottom">
        <div className="side-note">EVIDENCE-LED REPORTING<p>Estimates are not certified or assured. Verify your reporting boundaries and factor sources.</p></div>
        <button className="profile-button" onClick={logout}><span className="avatar">{user?.email.charAt(0).toUpperCase() || "R"}</span><span>{user?.organisation || "Workspace"}<small>Sign out ↗</small></span></button>
      </div>
    </aside>
    <main className="workspace">
      <div className="topbar"><span>WORKSPACE <b>/</b> {section.toUpperCase()}</span><span className="top-right"><i /> PILOT ACCESS <span className="separator" /> {user?.email || "Loading…"}</span></div>
      <div className="page-inner">
        {error && <div className="alert error" role="alert">{error}<button onClick={() => setError("")}>×</button></div>}
        {notice && <div className="alert success">{notice}<button onClick={() => setNotice("")}>×</button></div>}
        {catalog?.warning && <div className="factor-warning"><strong>Data provenance notice</strong><span>{catalog.warning} <a target="_blank" rel="noreferrer" href={catalog.official_2026_url}>Official 2026 source ↗</a></span></div>}
        {section === "overview" && <>
          <div className="page-heading"><div><div className="eyebrow accent">YOUR CARBON PICTURE</div><h1>Overview<span className="dot">.</span></h1><p>Reviewed activity data in one transparent place.</p></div><button className="btn primary" onClick={() => setSection("activities")}>+ New activity</button></div>
          <div className="stat-grid">
            <div className="stat-card main-stat"><span>TOTAL REPORTED ESTIMATE</span><strong>{number(summary?.total_tonnes_co2e || 0)} <small>tCO₂e</small></strong><div>Approved activity records only</div></div>
            <div className="stat-card"><span>REVIEWED RECORDS</span><strong>{summary?.approved_activity_count || 0}</strong><div>In the draft inventory</div></div>
            <div className="stat-card"><span>AWAITING REVIEW</span><strong>{drafts}</strong><div>Unapproved activity entries</div></div>
          </div>
          <div className="block-head"><div><h2>Emissions by scope</h2><p>Only approved entries count toward the totals</p></div><div className="mini-pill">kg CO₂e</div></div>
          <div className="scope-grid">{["Scope 1", "Scope 2", "Scope 3"].map((scope, index) => <div className="scope-card" key={scope}><div className="scope-index">0{index + 1}</div><h3>{scope}</h3><strong>{number(summary?.scope_emissions[scope] || 0)}</strong><div className="meter"><span style={{ width: Math.max(0, Math.min(100, ((summary?.scope_emissions[scope] || 0) / Math.max(summary?.total_kg_co2e || 0, 1)) * 100)) + "%" }} /></div></div>)}</div>
          <div className="surface summary-surface"><div><div className="label-soft">REPORTING OUTPUT</div><h2>Draft inventory exports</h2><p>Every row includes its factor vintage, physical activity and evidence reference. Not a UK SRS compliance certificate.</p></div><div className="button-stack"><button disabled={busy} className="btn dark" onClick={() => exportReport("/api/reports/html", "regtech-draft-inventory.html")}>↓ HTML report</button><button disabled={busy} className="btn outline" onClick={() => exportReport("/api/reports/csv", "regtech-activities.csv")}>↓ CSV export</button></div></div>
        </>}
        {section === "activities" && <>
          <div className="page-heading"><div><div className="eyebrow accent">ACTIVITY ACCOUNTING</div><h1>Activity ledger<span className="dot">.</span></h1><p>Specify the physical quantity and matching factor. Review before approval.</p></div></div>
          <form className="surface activity-form" onSubmit={submitActivity}>
            <div className="panel-heading"><h2>{editingId ? "Edit draft activity" : "Record an activity"}</h2><span className="mini-pill">HUMAN REVIEW REQUIRED</span></div>
            <div className="field-grid">
              <label className="span-2">Activity description<input required minLength={3} value={form.description} placeholder="e.g. Electricity consumed in April" onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
              <label>Supplier / source<input value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} placeholder="e.g. Utility provider" /></label>
              <label>Activity date<input type="date" value={form.activity_date} onChange={(e) => setForm({ ...form, activity_date: e.target.value })} /></label>
              <label className="span-2">Emission factor<select required value={form.factor_id} onChange={(e) => chooseFactor(e.target.value)}><option value="">Select a physical activity factor</option>{supported.map((factor) => <option key={factor.id} value={factor.id}>{factor.name} · {factor.id} ({factor.unit})</option>)}</select></label>
              <label>Activity quantity<input required min="0.000001" step="any" type="number" value={form.quantity} placeholder="Enter measured quantity" onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label>
              <label>Unit<input value={form.unit} readOnly placeholder="From selected factor" /></label>
              <label className="span-2">Scope / ownership (must verify)<select required value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}><option value="">Choose after verifying ownership and emissions boundary</option><option>Scope 1</option><option>Scope 2</option><option>Scope 3</option></select></label>
              <label className="span-2">Evidence reference<input required minLength={3} value={form.evidence_reference} onChange={(e) => setForm({ ...form, evidence_reference: e.target.value })} placeholder="Invoice number / page / meter reading / source record" /></label>
            </div>
            <div className="form-bottom"><p>No price-to-kWh or price-to-litres estimates. The full data source must be reviewed.</p><div>{editingId && <button type="button" className="btn outline" onClick={() => { setForm(blank()); setEditingId(""); }}>Cancel edit</button>}<button disabled={busy} className="btn primary">{busy ? "Saving…" : editingId ? "Update draft →" : "Save as draft →"}</button></div></div>
          </form>
          <div className="block-head"><div><h2>Recorded activities</h2><p>Approve a reviewed record to include it in reports</p></div><span className="mini-pill">{activities.length} RECORDS</span></div>
          <div className="surface ledger"><div className="table-scroll"><table><thead><tr><th>ACTIVITY</th><th>FACTOR</th><th>QUANTITY</th><th>EMISSIONS</th><th>STATUS / ACTION</th></tr></thead><tbody>{activities.map((activity) => <tr key={activity.id}><td><strong>{activity.description}</strong><small>{activity.evidence_reference}</small></td><td>{activity.factor_id}<small>{activity.scope} · {activity.factor_year}</small></td><td>{number(activity.quantity)} {activity.unit}</td><td><strong>{number(activity.emissions_kg_co2e)} kg</strong></td><td><span className={"status " + activity.status}>{activity.status}</span><div className="actions">{activity.status === "draft" && <><button disabled={busy} onClick={() => { setEditingId(activity.id); setForm({ description: activity.description, supplier: activity.supplier, activity_date: activity.activity_date, factor_id: activity.factor_id, quantity: String(activity.quantity), unit: activity.unit, scope: activity.scope, evidence_reference: activity.evidence_reference }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button><button disabled={busy} onClick={() => statusChange(activity.id, "approve")}>Approve</button></>}{activity.status !== "void" && <button disabled={busy} onClick={() => statusChange(activity.id, "void")}>Void</button>}</div></td></tr>)}</tbody></table>{activities.length === 0 && <div className="empty">No activity entries yet. Add an activity with supporting evidence above.</div>}</div></div>
        </>}
        {section === "documents" && <>
          <div className="page-heading"><div><div className="eyebrow accent">DOCUMENT INTELLIGENCE</div><h1>Document review<span className="dot">.</span></h1><p>Extract suggestions from invoices. Nothing is saved automatically.</p></div></div>
          <form className="surface upload-area" onSubmit={processDocument}><div className="upload-icon">↥</div><h2>Upload an invoice</h2><p>PDF, PNG or JPG · Maximum 8MB · PDFs maximum 5 pages</p><label className="file-picker">{doc ? doc.name : "Choose a document"}<input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => { setDoc(e.target.files?.[0] || null); setHints(null); }} /></label><button disabled={busy || !doc} className="btn primary">{busy ? "Reading…" : "Extract data suggestions →"}</button><small>OCR may require server-side Tesseract and Poppler. Failed extraction never returns fake sample data.</small></form>
          {hints && <div className="surface extract-result"><div className="label-soft">EXTRACTION RESULTS · REVIEW REQUIRED</div><h2>Document evidence hints</h2><p>{hints.warning}</p><div className="hint-meta"><div>Supplier <b>{hints.extracted.supplier || "Unknown"}</b></div><div>Invoice total <b>{hints.extracted.amount_gbp === null ? "Not found" : "£" + number(hints.extracted.amount_gbp)}</b></div><div>Date <b>{hints.extracted.date || "Unknown"}</b></div></div><h3>Physical quantities found</h3>{hints.extracted.activity_hints.length === 0 ? <p>No measured quantities found. Record the verified quantities manually.</p> : hints.extracted.activity_hints.map((hint, index) => <div className="hint-row" key={index}><span>{number(hint.quantity)} {hint.unit} <small>Source text: {hint.evidence}</small></span><button className="btn outline" onClick={() => applyDocumentHint(hint)}>Review as activity →</button></div>)}<details><summary>View OCR text preview</summary><pre>{hints.text_preview}</pre></details></div>}
        </>}
        <footer><span>RegTech Carbon Workspace · Pilot version 0.2</span><span>Draft estimates only — not regulatory assurance</span></footer>
      </div>
    </main>
  </div>;
}
