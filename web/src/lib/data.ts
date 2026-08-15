import { supabase } from "./supabase";
import type { Health, Latest, Obs } from "./types";

const DAY = 86_400_000;

export async function latestAll(): Promise<Map<string, Latest>> {
  const { data, error } = await supabase().from("latest_observations").select("*");
  if (error) throw error;
  return new Map((data as Latest[]).map((r) => [r.series_id, r]));
}

/** History for a set of series since `days` ago, ascending by ts. */
export async function history(ids: string[], days: number, withMeta = false): Promise<Map<string, Obs[]>> {
  if (ids.length === 0) return new Map();
  const since = new Date(Date.now() - days * DAY).toISOString();
  const cols = withMeta ? "series_id,ts,value,as_of,meta" : "series_id,ts,value";
  const { data, error } = await supabase()
    .from("observations")
    .select(cols)
    .in("series_id", ids)
    .gte("ts", since)
    .order("ts", { ascending: true })
    .limit(20000);
  if (error) throw error;
  const out = new Map<string, Obs[]>();
  for (const r of data as unknown as Obs[]) {
    if (!out.has(r.series_id)) out.set(r.series_id, []);
    out.get(r.series_id)!.push(r);
  }
  return out;
}

/** Latest observation (with meta) per series in a family, e.g. prefix 'au.rba.implied.' */
export async function latestWithMeta(prefix: string, days = 7): Promise<Obs[]> {
  const since = new Date(Date.now() - days * DAY).toISOString();
  const { data, error } = await supabase()
    .from("observations")
    .select("series_id,ts,value,as_of,meta")
    .like("series_id", `${prefix}%`)
    .gte("ts", since)
    .order("ts", { ascending: false })
    .limit(2000);
  if (error) throw error;
  const seen = new Map<string, Obs>();
  for (const r of data as unknown as Obs[]) if (!seen.has(r.series_id)) seen.set(r.series_id, r);
  return [...seen.values()];
}

export async function health(): Promise<Health[]> {
  const { data, error } = await supabase().from("adapter_health").select("*").order("adapter");
  if (error) throw error;
  return data as Health[];
}

export async function seriesCatalogue() {
  const { data, error } = await supabase()
    .from("series")
    .select("id,name,unit,asset_class,country,frequency,tier,source,source_ref,description,active,tags")
    .order("id");
  if (error) throw error;
  return data as Array<{
    id: string; name: string; unit: string; asset_class: string; country: string; frequency: string;
    tier: string; source: string; source_ref: string; description: string; active: boolean; tags: string[];
  }>;
}
