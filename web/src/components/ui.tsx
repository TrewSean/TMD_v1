import { TIER_LABEL, ago, fmtDelta, fmtTime, fmtValue } from "@/lib/format";
import type { Latest } from "@/lib/types";

export function Section({ title, kicker, right, children }: { title: string; kicker?: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="pt-10">
      <div className="flex items-baseline justify-between hair-b pb-2 mb-4">
        <div>
          {kicker && <div className="label mb-1">{kicker}</div>}
          <h2 className="text-[17px] font-semibold tracking-tight">{title}</h2>
        </div>
        {right && <div className="text-[12px] text-muted">{right}</div>}
      </div>
      {children}
    </section>
  );
}

export function TierBadge({ tier }: { tier: string }) {
  return <span className="label" title={tier === "primary" ? "Publisher of record" : tier === "feed" ? "Licensed market data feed" : "Delayed or unofficial aggregator"}>{TIER_LABEL[tier] ?? tier}</span>;
}

export function Delta({ delta, unit }: { delta: number | null; unit: string }) {
  const d = fmtDelta(delta, unit);
  if (!d) return <span className="text-muted">–</span>;
  const cls = d.dir === "up" ? "text-up" : d.dir === "down" ? "text-down" : "text-ink-2";
  return <span className={`num ${cls}`}>{d.text}</span>;
}

/** Stat tile: label, value, delta vs a named period, as-of. */
export function Tile({ row, delta, deltaLabel = "1d", nameOverride }: { row: Latest | undefined; delta: number | null; deltaLabel?: string; nameOverride?: string }) {
  if (!row) return (
    <div className="py-4 pr-6">
      <div className="text-[13px] text-ink-2">{nameOverride ?? "–"}</div>
      <div className="text-[22px] text-muted mt-1">–</div>
    </div>
  );
  return (
    <div className="py-4 pr-6">
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-[13px] text-ink-2 truncate">{nameOverride ?? row.name}</div>
        <TierBadge tier={row.tier} />
      </div>
      <div className="flex items-baseline gap-3 mt-1">
        <div className="text-[24px] font-semibold tracking-tight">{fmtValue(row.value, row.unit)}</div>
        <div className="text-[13px]"><Delta delta={delta} unit={row.unit} /> <span className="text-muted">{deltaLabel}</span></div>
      </div>
      <div className="text-[11px] text-muted mt-1 num" title={`Value time ${fmtTime(row.ts)}, fetched ${fmtTime(row.as_of)}`}>{fmtTime(row.ts)} · {ago(row.as_of)}</div>
    </div>
  );
}

export function TileGrid({ children, cols = 4 }: { children: React.ReactNode; cols?: number }) {
  const cls = cols === 3 ? "grid-cols-1 sm:grid-cols-3" : cols === 2 ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-2 lg:grid-cols-4";
  return <div className={`grid ${cls} gap-x-8 divide-y divide-hair sm:divide-y-0`}>{children}</div>;
}

export function Table({ head, rows, align = [], widths = [] }: { head: string[]; rows: React.ReactNode[][]; align?: ("l" | "r")[]; widths?: (string | undefined)[] }) {
  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="hair-b">
          {head.map((h, i) => (
            <th key={i} style={widths[i] ? { width: widths[i] } : undefined} className={`py-2 font-normal label ${align[i] === "r" ? "text-right" : "text-left"}`}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="hair-b last:border-0">
            {r.map((c, j) => (
              <td key={j} className={`py-2 num ${align[j] === "r" ? "text-right" : "text-left"}`}>{c}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-[12px] text-ink-2 leading-relaxed mt-4 max-w-[70ch]">{children}</p>;
}
