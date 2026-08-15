import { history, latestAll, latestWithMeta } from "@/lib/data";
import { changeOver } from "@/lib/changes";
import { Note, Section, Table, Tile, TileGrid, TierBadge } from "@/components/ui";
import ImpliedPathCard from "@/components/ImpliedPathCard";
import LineChart from "@/components/LineChart";
import { fmtDate, fmtTime } from "@/lib/format";
import type { Latest } from "@/lib/types";

export const revalidate = 60;

const AU_TILES = ["au.rba.cash_rate_target", "au.rba.cash_rate_interbank", "au.bbsw.1m", "au.bbsw.3m", "au.bbsw.6m", "au.acgb.2y", "au.acgb.3y", "au.acgb.10y"];
const US_TILES = ["us.nyfed.effr", "us.nyfed.sofr", "us.ust.par.3m", "us.ust.par.2y", "us.ust.par.5y", "us.ust.par.10y", "us.ust.par.30y", "us.ust.cboe.10y"];
const TENOR_YEARS: Record<string, number> = { "1m": 1 / 12, "2m": 2 / 12, "3m": 0.25, "4m": 4 / 12, "6m": 0.5, "1y": 1, "2y": 2, "3y": 3, "5y": 5, "7y": 7, "10y": 10, "20y": 20, "30y": 30 };
const HIST = ["au.rba.cash_rate_target", "au.bbsw.3m", "au.acgb.3y", "au.acgb.10y", "us.ust.par.2y", "us.ust.par.10y", "us.nyfed.sofr"];

function curve(latest: Map<string, Latest>, prefix: string) {
  const pts: { tenor: string; years: number; y: number; row: Latest }[] = [];
  for (const [id, r] of latest) {
    if (!id.startsWith(prefix)) continue;
    const t = id.slice(prefix.length);
    if (!(t in TENOR_YEARS)) continue;
    pts.push({ tenor: t, years: TENOR_YEARS[t], y: parseFloat(r.value), row: r });
  }
  return pts.sort((a, b) => a.years - b.years);
}

export default async function Rates() {
  const [latest, hist, rba, fed] = await Promise.all([
    latestAll(), history([...AU_TILES, ...US_TILES, ...HIST], 400), latestWithMeta("au.rba.implied."), latestWithMeta("us.fed.implied."),
  ]);
  const d1 = (id: string) => { const r = latest.get(id); return r ? changeOver(hist.get(id) ?? [], 1, r.unit) : null; };
  const au = curve(latest, "au.acgb."), us = curve(latest, "us.ust.par.");
  // Ordinal x: one slot per tenor present on either curve, so the short end is readable.
  const tenors = Object.keys(TENOR_YEARS).filter((t) => au.some((p) => p.tenor === t) || us.some((p) => p.tenor === t));
  const spreads = au.map((a) => { const u = us.find((x) => x.tenor === a.tenor); return u ? { tenor: a.tenor, au: a.y, us: u.y, bp: (a.y - u.y) * 100 } : null; }).filter(Boolean) as { tenor: string; au: number; us: number; bp: number }[];
  const slope = (c: typeof au, s: string, l: string) => { const a = c.find((x) => x.tenor === s), b = c.find((x) => x.tenor === l); return a && b ? ((b.y - a.y) * 100).toFixed(0) : "–"; };
  const line = (id: string, name: string, color: string) => ({ name, color, points: (hist.get(id) ?? []).map((o) => ({ x: new Date(o.ts).getTime(), y: parseFloat(o.value) })) });

  return (
    <>
      <div className="pt-10 pb-2"><h1 className="text-[26px] font-semibold tracking-tight">Rates desk</h1></div>

      <Section title="Australia" kicker="RBA F1 and F2, daily" right={latest.get("au.rba.cash_rate_target") ? `Fixings as at ${fmtDate(latest.get("au.rba.cash_rate_target")!.ts)}` : ""}>
        <TileGrid cols={4}>{AU_TILES.map((id) => <Tile key={id} row={latest.get(id)} delta={d1(id)} />)}</TileGrid>
      </Section>

      <Section title="United States" kicker="Treasury par yields, NY Fed reference rates" right={latest.get("us.ust.par.10y") ? `Par curve as at ${fmtDate(latest.get("us.ust.par.10y")!.ts)}` : ""}>
        <TileGrid cols={4}>{US_TILES.map((id) => <Tile key={id} row={latest.get(id)} delta={d1(id)} />)}</TileGrid>
      </Section>

      <Section title="Government yield curves" kicker="ACGB vs US Treasury par" right={`2s10s AU ${slope(au, "2y", "10y")}bp · US ${slope(us, "2y", "10y")}bp`}>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-x-12 gap-y-6">
          <LineChart
            xKind="years" yDp={2} yUnit="%"
            xTicks={tenors.map((_, i) => i)} xTickLabels={Object.fromEntries(tenors.map((t, i) => [i, t]))}
            series={[
              { name: "Australia (ACGB)", color: "var(--series-1)", points: au.map((p) => ({ x: tenors.indexOf(p.tenor), y: p.y })) },
              { name: "United States (par)", color: "var(--series-2)", points: us.map((p) => ({ x: tenors.indexOf(p.tenor), y: p.y })) },
            ]}
          />
          <Table head={["Tenor", "AU", "US", "AU − US"]} align={["l", "r", "r", "r"]}
            rows={spreads.map((s) => [s.tenor, s.au.toFixed(2) + "%", s.us.toFixed(2) + "%", (s.bp > 0 ? "+" : "") + s.bp.toFixed(0) + "bp"])} />
        </div>
        <Note>ACGB from RBA table F2 (2, 3, 5, 10 year interpolated yields). US from the Treasury daily par yield curve, 13 tenors. Both are end-of-day fixings; tenors are evenly spaced, not to scale.</Note>
      </Section>

      <Section title="Implied RBA cash rate path" kicker="ASX 30-day interbank cash rate futures" right="Solved meeting by meeting from the monthly-average strip">
        <ImpliedPathCard title="RBA cash rate" nodes={rba} />
      </Section>

      <Section title="Implied fed funds path" kicker="CME 30-day fed funds futures (delayed quotes)" right="Effective rate, not the target range midpoint">
        <ImpliedPathCard title="Fed funds (EFFR)" nodes={fed} />
        <Note>Method: the rate is piecewise constant, changing only on each meeting&rsquo;s effective date; each contract&rsquo;s implied rate is the calendar-day weighted average across regimes; all meetings are solved jointly by ridge-regularised least squares that prefers no change where the data are silent. Nodes flagged weak sit at a month boundary and have little contract coverage. Expect ±1 to 3bp (RBA) and ±2 to 5bp (Fed) against a terminal. Not tradeable levels.</Note>
      </Section>

      <Section title="History" kicker="Last 12 months" right="Daily fixings">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-10">
          <div><div className="label mb-2">Australia · cash rate, 3m BBSW, 3y and 10y ACGB</div>
            <LineChart yUnit="%" series={[line("au.rba.cash_rate_target", "Cash rate", "var(--ink)"), line("au.bbsw.3m", "3m BBSW", "var(--series-3)"), line("au.acgb.3y", "3y ACGB", "var(--series-1)"), line("au.acgb.10y", "10y ACGB", "var(--series-2)")]} /></div>
          <div><div className="label mb-2">United States · SOFR, 2y and 10y Treasury</div>
            <LineChart yUnit="%" series={[line("us.nyfed.sofr", "SOFR", "var(--ink)"), line("us.ust.par.2y", "2y UST", "var(--series-1)"), line("us.ust.par.10y", "10y UST", "var(--series-2)")]} /></div>
        </div>
        <Note>History starts on 15 August 2026 (about 45 days of backfill from each publisher) and grows daily. A deeper backfill is on the plan.</Note>
      </Section>
      <div className="mt-8 text-[11px] text-muted">Tiers: <TierBadge tier="primary" /> publisher of record · <TierBadge tier="feed" /> licensed feed · <TierBadge tier="aggregator" /> delayed. Times shown in Sydney time; last page build {fmtTime(new Date().toISOString())}.</div>
    </>
  );
}
