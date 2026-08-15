export type Tier = "primary" | "feed" | "aggregator";

export interface Latest {
  series_id: string;
  name: string;
  unit: string;
  asset_class: string;
  country: string;
  frequency: string;
  tier: Tier;
  source: string;
  tags: string[];
  ts: string;
  value: string; // numeric comes back as string
  as_of: string;
}

export interface Obs {
  series_id: string;
  ts: string;
  value: string;
  as_of?: string;
  meta?: Record<string, string> | null;
}

export interface Health {
  adapter: string;
  status: "ok" | "partial" | "error";
  finished_at: string;
  rows_written: number;
  error: string | null;
}
