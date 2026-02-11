"use client";

import { useState, useEffect } from "react";
import {
  getSyntheticInvoices,
  processTransactions,
  processInvoice,
  getScorecardHtmlUrl,
  type Transaction,
  type Scorecard,
} from "@/lib/api";

function UploadZone({ onResult }: { onResult: (data: unknown) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && (f.type.startsWith("image/") || f.type === "application/pdf")) {
      setFile(f);
      setError(null);
    }
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      setError(null);
    }
  };

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await processInvoice(file);
      onResult(res);
    } catch (err) {
      setError("Failed to process. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-2 border-dashed border-teal-300 dark:border-teal-700 rounded-xl p-8 text-center bg-white dark:bg-slate-800">
      <p className="text-slate-600 dark:text-slate-400 mb-4">
        Upload invoice (PDF or image) for AI extraction & carbon calculation
      </p>
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border border-teal-200 dark:border-teal-600 rounded-lg p-6 mb-4"
      >
        <input
          type="file"
          accept="image/*,.pdf"
          onChange={handleFile}
          className="hidden"
          id="file-upload"
        />
        <label htmlFor="file-upload" className="cursor-pointer block">
          {file ? file.name : "Drop file here or click to select"}
        </label>
      </div>
      {file && (
        <button
          onClick={submit}
          disabled={loading}
          className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg disabled:opacity-50"
        >
          {loading ? "Processing…" : "Process"}
        </button>
      )}
      {error && <p className="text-red-500 mt-2">{error}</p>}
    </div>
  );
}

function ScorecardView({ scorecard }: { scorecard: Scorecard }) {
  const scopes = Object.entries(scorecard.scope_emissions);
  const categories = Object.entries(scorecard.breakdown_by_category).slice(0, 10);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scopes.map(([name, kg]) => (
          <div
            key={name}
            className="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
          >
            <p className="text-sm text-slate-500 dark:text-slate-400">{name}</p>
            <p className="text-2xl font-bold text-teal-600 dark:text-teal-400">
              {kg.toFixed(1)} kg CO2e
            </p>
          </div>
        ))}
      </div>
      <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
        <h3 className="text-lg font-semibold mb-4">Total: {scorecard.total_tonnes_co2e.toFixed(2)} tonnes CO2e</h3>
        <p className="text-sm text-slate-500 mb-4">
          {scorecard.transaction_count} transactions • UK SRS aligned
        </p>
        <h4 className="font-medium mb-2">Breakdown by category</h4>
        <ul className="space-y-1 text-sm">
          {categories.map(([cat, kg]) => (
            <li key={cat} className="flex justify-between">
              <span className="text-slate-600 dark:text-slate-400">{cat}</span>
              <span>{kg.toFixed(1)} kg</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function Home() {
  const [invoices, setInvoices] = useState<Transaction[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploadResult, setUploadResult] = useState<unknown>(null);

  useEffect(() => {
    async function load() {
      try {
        const inv = await getSyntheticInvoices();
        setInvoices(inv);
        const { scorecard: sc } = await processTransactions(inv.slice(0, 50));
        setScorecard(sc);
      } catch {
        setInvoices([]);
        setScorecard(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="min-h-screen">
      <header className="bg-teal-800 text-white py-6 px-6">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-bold">ESG RegTech Platform</h1>
          <p className="text-teal-200 text-sm mt-1">
            AI-powered ESG compliance for SMEs • UK SRS aligned
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6 space-y-8">
        <section>
          <h2 className="text-xl font-semibold mb-4">Upload Invoice</h2>
          <UploadZone onResult={(d) => setUploadResult(d)} />
          {uploadResult && (
            <div className="mt-4 p-4 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm">
              <pre className="whitespace-pre-wrap overflow-auto max-h-48">
                {JSON.stringify(uploadResult, null, 2)}
              </pre>
            </div>
          )}
        </section>

        <section>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">ESG Dashboard</h2>
            <a
              href={getScorecardHtmlUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm inline-block"
            >
              View Report (Print to PDF) →
            </a>
          </div>
          {loading ? (
            <p className="text-slate-500">Loading…</p>
          ) : scorecard ? (
            <ScorecardView scorecard={scorecard} />
          ) : (
            <p className="text-slate-500">
              No data. Start backend and run: python scripts/generate_synthetic_invoices.py
            </p>
          )}
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">Sample Transactions</h2>
          <div className="overflow-x-auto border border-slate-200 dark:border-slate-700 rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800">
                  <th className="text-left p-3">Supplier</th>
                  <th className="text-left p-3">Description</th>
                  <th className="text-right p-3">Amount</th>
                  <th className="text-left p-3">Category</th>
                  <th className="text-right p-3">Emissions (kg)</th>
                </tr>
              </thead>
              <tbody>
                {(scorecard?.transactions ?? invoices).slice(0, 15).map((inv, i) => (
                  <tr key={inv.id ?? i} className="border-t border-slate-200 dark:border-slate-700">
                    <td className="p-3">{inv.supplier}</td>
                    <td className="p-3">{inv.description}</td>
                    <td className="p-3 text-right">£{(inv.amount_gbp ?? 0).toFixed(2)}</td>
                    <td className="p-3">{inv.category ?? "—"}</td>
                    <td className="p-3 text-right">{inv.emissions_kg_co2e?.toFixed(1) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <footer className="text-center text-slate-500 text-sm py-8">
          ESG RegTech Platform • UK SRS aligned • DEFRA conversion factors 2024
        </footer>
      </main>
    </div>
  );
}
