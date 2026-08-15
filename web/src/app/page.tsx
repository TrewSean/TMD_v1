import { history, latestAll } from "@/lib/data";
import { changeOver } from "@/lib/changes";
import { Note, Section, Tile, TileGrid } from "@/components/ui";
import { fmtTime } from "@/lib/format";
import ImpliedPathCard from "@/components/ImpliedPathCard";
import { latestWithMeta } from "@/lib/data";

export const revalidate = 60;

const AU = ["au.rba.cash_rate_target", "au.bbsw.3m", "au.acgb.3y", "au.acgb.10y"];
const US = ["us.nyfed.effr", "us.nyfed.sofr", "us.ust.par.2y", "us.ust.par.10y"];
const MKT = ["au.asx200", "us.spx", "us.ndx", "us.vix", "fx.audusd", "fx.dxy", "cmd.wti", "cmd.gold"];

export default async function Overview() {
  const [latest, hist, rba, fed] = await Promise.all([
    latestAll(),
    history([...AU, ...US, ...MKT], 12),
    latestWithMeta("au.rba.implied."),
    latestWithMeta("us.fed.implied."),
  ]);
  const d1 = (id: string) => { const r = latest.get(id); return r ? changeOver(hist.get(id) ?? [], 1, r.unit) : null; };
  const newest = [...latest.values()].map((r) => r.as_of).sort().at(-1);

  return (
    <>
      <div className="pt-10 pb-2 flex items-baseline justify-between">
        <h1 className="text-[26px] font-semibold tracking-tight">Overview</h1>
        {newest && <div className="text-[12px] text-muted num">Last update {fmtTime(newest)}</div>}
      </div>

      <Section title="Rates" kicker="Australia and United States" right="Daily fixings from RBA, US Treasury and NY Fed">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12">
          <div>
            <div className="label pt-2">Australia</div>
            <TileGrid cols={2}>{AU.map((id) => <Tile key={id} row={latest.get(id)} delta={d1(id)} />)}</TileGrid>
          </div>
          <div>
            <div className="label pt-2">United States</div>
            <TileGrid cols={2}>{US.map((id) => <Tile key={id} row={latest.get(id)} delta={d1(id)} />)}</TileGrid>
          </div>
        </div>
      </Section>

      <Section title="Policy paths" kicker="Implied by futures" right="ASX 30-day interbank futures · CME fed funds futures">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-8">
          <ImpliedPathCard title="RBA cash rate" nodes={rba} compact />
          <ImpliedPathCard title="Fed funds (effective)" nodes={fed} compact />
        </div>
      </Section>

      <Section title="Markets" kicker="Equities, FX, commodities" right="Delayed 10 to 20 min">
        <TileGrid cols={4}>{MKT.map((id) => <Tile key={id} row={latest.get(id)} delta={d1(id)} />)}</TileGrid>
        <Note>Change is versus the last observation at least one day earlier, never interpolated. Badges show the source tier: Primary is the publisher of record, Feed is a licensed market data feed, Delayed is an aggregator.</Note>
      </Section>
    </>
  );
}
