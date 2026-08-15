import type { Obs } from "@/lib/types";
import BarChart from "./BarChart";
import { Table } from "./ui";
import { fmtDate } from "@/lib/format";

function nodeIndex(id: string) { const m = id.match(/\.n(\d+)$/); return m ? parseInt(m[1]) : 999; }

export default function ImpliedPathCard({ title, nodes, compact = false }: { title: string; nodes: Obs[]; compact?: boolean }) {
  const sorted = [...nodes].sort((a, b) => nodeIndex(a.series_id) - nodeIndex(b.series_id));
  if (sorted.length === 0) return <div className="text-[12px] text-muted">No implied path yet.</div>;
  const m0 = sorted[0].meta ?? {};
  const current = parseFloat(m0.current_rate ?? "NaN");
  const asOf = m0.valuation_date;
  const rms = m0.fit_rms_bp;
  const shown = compact ? sorted.slice(0, 8) : sorted;

  const bars = shown.map((n) => ({
    label: shortDate(n.meta?.meeting_date ?? ""),
    value: parseFloat(n.meta?.change_from_current_bp ?? "0"),
    sub: `${parseFloat(n.value).toFixed(2)}%`,
    muted: n.meta?.weak === "true",
  }));

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-[13px] text-ink-2">{title} <span className="text-muted">· current {isFinite(current) ? current.toFixed(2) + "%" : "–"}</span></div>
        <div className="text-[11px] text-muted num">as at {asOf ? fmtDate(asOf) : "–"} · fit {rms}bp</div>
      </div>
      <BarChart bars={bars} height={compact ? 170 : 240} width={compact ? 720 : 1130} ySigned yUnit="bp" />
      {!compact && (
        <div className="mt-4">
          <Table
            head={["Meeting", "Implied", "Δ vs now", "Step", "Moves priced", "Move prob.", "Fit"]}
            align={["l", "r", "r", "r", "r", "r", "r"]}
            rows={sorted.map((n) => {
              const m = n.meta ?? {};
              const p = parseFloat(m.prob_move_at_meeting ?? "0");
              return [
                <span key="d">{m.meeting_date ? fmtDate(m.meeting_date) : n.series_id}</span>,
                `${parseFloat(n.value).toFixed(3)}%`,
                signed(m.change_from_current_bp) + "bp",
                signed(m.step_bp) + "bp",
                signed(m.cumulative_moves, 2),
                `${Math.round(Math.abs(p) * 100)}% ${p > 0 ? "hike" : p < 0 ? "cut" : ""}`.trim(),
                m.weak === "true" ? <span key="w" className="text-muted">weak</span> : <span key="w" className="text-muted">ok</span>,
              ];
            })}
          />
        </div>
      )}
    </div>
  );
}

function signed(s: string | undefined, dp = 1) { const v = parseFloat(s ?? "NaN"); if (!isFinite(v)) return "–"; return (v > 0 ? "+" : "") + v.toFixed(dp); }
function shortDate(iso: string) { if (!iso) return ""; const d = new Date(iso + "T00:00:00Z"); return d.toLocaleDateString("en-AU", { timeZone: "UTC", day: "numeric", month: "short" }); }
