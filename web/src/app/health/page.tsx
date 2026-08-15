import { health, seriesCatalogue } from "@/lib/data";
import { Note, Section, Table, TierBadge } from "@/components/ui";
import { ago, fmtTime } from "@/lib/format";

export const revalidate = 60;

const DESC: Record<string, string> = {
  rba_f1: "RBA statistical table F1: cash rate, AONIA, BBSW, OIS. Daily.",
  rba_f2: "RBA statistical table F2: ACGB yields. Daily.",
  ust_par: "US Treasury daily par yield curve. Daily.",
  nyfed_rates: "NY Fed reference rates: SOFR, EFFR. Daily.",
  asx_rate_tracker: "ASX 30-day interbank cash rate futures strip and RBA Rate Tracker. Daily.",
  fed_funds_futures: "CME 30-day fed funds futures via Yahoo. Daily, delayed.",
  yfinance: "Yahoo Finance snapshots: indices, FX, commodities, CBOE yields. Every 30 min, delayed.",
  alpaca: "Alpaca latest bars (polling). Every 30 min.",
  alpaca_stream: "Alpaca websocket worker heartbeat. Every 5 min when running.",
  derive_rba: "Implied RBA path solved from the ASX strip.",
  derive_fed: "Implied fed funds path solved from the CME strip.",
};

export default async function Health() {
  const [h, series] = await Promise.all([health(), seriesCatalogue()]);
  const active = series.filter((s) => s.active);
  return (
    <>
      <div className="pt-10 pb-2"><h1 className="text-[26px] font-semibold tracking-tight">Sources and health</h1></div>
      <Section title="Last run per source" kicker="ingest_runs" right="No AI at run time; every job is plain code on a schedule">
        <Table head={["Source", "Status", "Last run", "Rows", "What it is"]} align={["l", "l", "r", "r", "l"]}
          rows={h.map((r) => [
            <span key="a" className="font-medium">{r.adapter}</span>,
            <span key="s" className={r.status === "ok" ? "text-up" : r.status === "partial" ? "text-ink-2" : "text-down"}>{r.status}{r.error ? ` · ${r.error.slice(0, 80)}` : ""}</span>,
            <span key="t" title={fmtTime(r.finished_at)}>{ago(r.finished_at)}</span>,
            r.rows_written,
            <span key="d" className="text-ink-2">{DESC[r.adapter] ?? ""}</span>,
          ])} />
        <Note>Schedules (Sydney time, weekdays): fixings at about 5:15pm, 11:30pm and 7:30am; markets snapshots every 30 minutes; the Alpaca worker streams continuously when deployed. GitHub Actions can run a few minutes late at busy times; the as-at time on each figure is authoritative.</Note>
      </Section>
      <Section title="Series catalogue" kicker={`${active.length} active series`} right="Every number on this site is one of these">
        <Table head={["Id", "Name", "Unit", "Source", "Frequency", "Tier"]} align={["l", "l", "l", "l", "l", "r"]}
          rows={active.map((s) => [<code key="i" className="text-[12px]">{s.id}</code>, s.name, s.unit, s.source, s.frequency, <TierBadge key="t" tier={s.tier} />])} />
      </Section>
    </>
  );
}
