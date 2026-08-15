import { history, latestAll } from "@/lib/data";
import { changeOver } from "@/lib/changes";
import { Note, Section, Table, Tile, TileGrid, TierBadge, Delta } from "@/components/ui";
import { ago, fmtTime, fmtValue } from "@/lib/format";

export const revalidate = 60;

const IDX = ["au.asx200", "us.spx", "us.ndx", "us.djia", "us.vix"];
const FX = ["fx.audusd", "fx.dxy"];
const CMD = ["cmd.wti", "cmd.brent", "cmd.gold", "cmd.copper"];
const ETF = ["us.etf.spy", "us.etf.qqq", "us.etf.dia", "us.etf.iwm", "us.etf.tlt", "us.etf.ief", "us.etf.gld", "us.etf.uso"];
const TECH = ["us.stk.nvda", "us.stk.aapl", "us.stk.msft", "us.stk.amd", "us.stk.tsla", "us.stk.avgo", "us.stk.tsm"];

export default async function Markets() {
  const all = [...IDX, ...FX, ...CMD, ...ETF, ...TECH];
  const [latest, hist] = await Promise.all([latestAll(), history(all, 10)]);
  const ch = (id: string, days: number) => { const r = latest.get(id); return r ? changeOver(hist.get(id) ?? [], days, r.unit) : null; };
  const rows = (ids: string[]) => ids.map((id) => { const r = latest.get(id); return r ? [
    r.name, fmtValue(r.value, r.unit), <Delta key="1" delta={ch(id, 1)} unit={r.unit} />, <Delta key="7" delta={ch(id, 7)} unit={r.unit} />, <span key="t" className="text-muted">{fmtTime(r.ts)} · {ago(r.as_of)}</span>, <TierBadge key="b" tier={r.tier} />,
  ] : [id, "–", "–", "–", "–", ""]; });
  const head = ["", "Last", "1d", "1w", "As at", ""];
  const align: ("l" | "r")[] = ["l", "r", "r", "r", "r", "r"];
  const widths = ["30%", "12%", "12%", "12%", "24%", "10%"];

  return (
    <>
      <div className="pt-10 pb-2"><h1 className="text-[26px] font-semibold tracking-tight">Markets</h1></div>
      <Section title="Indices, FX, commodities" kicker="Snapshots every 30 minutes" right="Yahoo Finance, delayed 10 to 20 min">
        <TileGrid cols={4}>{[...IDX, ...FX, ...CMD].slice(0, 8).map((id) => <Tile key={id} row={latest.get(id)} delta={ch(id, 1)} />)}</TileGrid>
        <div className="mt-6"><Table head={head} align={align} widths={widths} rows={rows([...IDX, ...FX, ...CMD])} /></div>
      </Section>
      <Section title="US ETFs" kicker="Alpaca feed" right="Index, Treasury and commodity proxies">
        <Table head={head} align={align} widths={widths} rows={rows(ETF)} />
      </Section>
      <Section title="Tech and AI" kicker="Alpaca feed">
        <Table head={head} align={align} widths={widths} rows={rows(TECH)} />
        <Note>Alpaca prices are the last 1-minute bar close on the IEX feed (real-time but a partial view of US volume). Yahoo figures are delayed. Neither is a pricing source.</Note>
      </Section>
    </>
  );
}
