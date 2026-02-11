const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Transaction {
  id?: string;
  supplier?: string;
  description: string;
  amount_gbp: number;
  quantity?: number;
  unit?: string;
  category?: string;
  emissions_kg_co2e?: number;
  scope?: string;
  date?: string;
}

export interface CarbonResult {
  category: string;
  emissions_kg_co2e: number;
  scope: string;
}

export interface Scorecard {
  report_date: string;
  standards: string;
  scope_emissions: Record<string, number>;
  total_kg_co2e: number;
  total_tonnes_co2e: number;
  transaction_count: number;
  breakdown_by_category: Record<string, number>;
  transactions: Transaction[];
}

export async function getSyntheticInvoices(): Promise<Transaction[]> {
  const res = await fetch(`${API_BASE}/api/synthetic-invoices`);
  if (!res.ok) throw new Error("Failed to fetch invoices");
  return res.json();
}

export async function processTransactions(transactions: Transaction[]): Promise<{
  transactions: Transaction[];
  scorecard: Scorecard;
}> {
  const res = await fetch(`${API_BASE}/api/process-transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(transactions),
  });
  if (!res.ok) throw new Error("Failed to process transactions");
  return res.json();
}

export async function processInvoice(file: File): Promise<{
  extracted: { supplier?: string; amount?: number; description?: string; category?: string };
  carbon_result: CarbonResult | null;
  text_preview: string;
}> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/process-invoice`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to process invoice");
  return res.json();
}

export function getScorecardHtmlUrl(): string {
  return `${API_BASE}/api/scorecard-html`;
}
