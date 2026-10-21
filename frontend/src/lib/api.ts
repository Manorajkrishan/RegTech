export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Factor = {
  id: string; name: string; unit: string; factor: number;
  suggested_scope?: string; supported: boolean;
};
export type FactorCatalog = {
  factor_year: number; source: string; official_2026_url: string;
  warning: string; factors: Factor[];
};
export type Activity = {
  id: string; created_by: string; description: string; supplier: string; activity_date: string;
  factor_id: string; factor_year: number; factor_value: number;
  quantity: number; unit: string; scope: string;
  emissions_kg_co2e: number; evidence_reference: string; status: string;
};
export type Summary = {
  organisation: string; generated_at: string; status: string; disclaimer: string;
  scope_emissions: Record<string, number>; total_kg_co2e: number;
  total_tonnes_co2e: number; approved_activity_count: number;
  factor_years: number[];
  breakdown_by_factor: Record<string, number>;
};
export type InvoiceHints = {
  extracted: {
    supplier: string | null; amount_gbp: number | null; date: string | null;
    activity_hints: { quantity: number; unit: string; evidence: string }[];
    needs_review: boolean; note: string;
  };
  text_preview: string; stored: boolean; warning: string;
};

export async function api<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", "Bearer " + token);
  const response = await fetch(API_BASE + path, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    let error: { detail?: string } = {};
    try { error = await response.json(); } catch {}
    throw new Error(typeof error.detail === "string" ? error.detail : "Request failed: " + response.status);
  }
  return response.json() as Promise<T>;
}

export async function download(token: string, path: string, filename: string) {
  const response = await fetch(API_BASE + path, {
    headers: { Authorization: "Bearer " + token }, cache: "no-store"
  });
  if (!response.ok) throw new Error("Could not generate report: " + response.status);
  const url = URL.createObjectURL(await response.blob());
  const element = document.createElement("a");
  element.href = url;
  element.download = filename;
  element.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
