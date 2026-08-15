const SYD = "Australia/Sydney";

export function fmtValue(v: string | number, unit: string): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (!isFinite(n)) return "–";
  switch (unit) {
    case "pct": return n.toFixed(2) + "%";
    case "bp": return n.toFixed(0) + "bp";
    case "pct_prob": return n.toFixed(0) + "%";
    case "index": return n >= 1000 ? n.toLocaleString("en-AU", { maximumFractionDigits: 0 }) : n.toFixed(2);
    case "price": return n >= 10 ? n.toFixed(2) : n >= 1 ? n.toFixed(3) : n.toFixed(4);
    case "usd_per_bbl": return n.toFixed(2);
    case "usd_per_oz": return n.toLocaleString("en-AU", { maximumFractionDigits: 0 });
    case "usd_per_lb": return n.toFixed(3);
    default: return n.toLocaleString("en-AU", { maximumFractionDigits: 4 });
  }
}

export function fmtDelta(delta: number | null, unit: string): { text: string; dir: "up" | "down" | "flat" } | null {
  if (delta === null || !isFinite(delta)) return null;
  const dir = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
  const a = Math.abs(delta);
  if (unit === "pct") return { text: `${sign}${(a * 100).toFixed(a * 100 < 10 ? 1 : 0)}bp`, dir };
  return { text: `${sign}${a.toFixed(2)}%`, dir }; // caller passes pct change for prices
}

export function fmtTime(iso: string, opts: { date?: boolean } = {}): string {
  const d = new Date(iso);
  const t = d.toLocaleTimeString("en-AU", { timeZone: SYD, hour: "2-digit", minute: "2-digit", hour12: false });
  const day = d.toLocaleDateString("en-AU", { timeZone: SYD, day: "numeric", month: "short" });
  return opts.date === false ? t : `${day} ${t}`;
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-AU", { timeZone: SYD, day: "numeric", month: "short", year: "numeric" });
}

export function ago(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400 * 2) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export const TIER_LABEL: Record<string, string> = { primary: "Primary", feed: "Feed", aggregator: "Delayed" };
