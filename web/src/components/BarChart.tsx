"use client";
import { useState } from "react";

export interface Bar { label: string; value: number; sub?: string; muted?: boolean }

/** Columns from a zero baseline (positive up, negative down), ≤24px thick, 4px rounded data-end, hover tooltip. */
export default function BarChart({ bars, color = "var(--series-1)", height = 200, width = 720, yDp = 0, ySigned = false, yUnit = "" }: { bars: Bar[]; color?: string; height?: number; width?: number; yDp?: number; ySigned?: boolean; yUnit?: string }) {
  const yFmt = (v: number) => (ySigned && v > 0 ? "+" : "") + v.toFixed(yDp);
  const W = width, H = height, PAD = { l: 44, r: 16, t: 14, b: 40 };
  const [hover, setHover] = useState<number | null>(null);
  if (bars.length === 0) return <div className="text-[12px] text-muted py-8">No data yet.</div>;
  const vals = bars.map((b) => b.value);
  let ymin = Math.min(0, ...vals), ymax = Math.max(0, ...vals);
  if (ymax === ymin) ymax = ymin + 1;
  const span = ymax - ymin; ymin -= span * 0.05; ymax += span * 0.1;
  const sy = (y: number) => PAD.t + (1 - (y - ymin) / (ymax - ymin)) * (H - PAD.t - PAD.b);
  const slot = (W - PAD.l - PAD.r) / bars.length;
  const bw = Math.min(24, slot * 0.6);
  const step = niceStep((ymax - ymin) / 4);
  const yt: number[] = []; for (let v = Math.ceil(ymin / step) * step; v <= ymax; v += step) yt.push(+v.toFixed(6));
  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" onMouseLeave={() => setHover(null)}>
        {yt.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={sy(v)} y2={sy(v)} stroke="var(--hair)" />
            <text x={PAD.l - 8} y={sy(v) + 3.5} fontSize={10.5} textAnchor="end" fill="var(--muted)" className="num">{yFmt(v)}{yUnit}</text>
          </g>
        ))}
        <line x1={PAD.l} x2={W - PAD.r} y1={sy(0)} y2={sy(0)} stroke="var(--axis)" />
        {bars.map((b, i) => {
          const cx = PAD.l + slot * (i + 0.5);
          const y0 = sy(0), y1 = sy(b.value);
          const top = Math.min(y0, y1), h = Math.max(1, Math.abs(y1 - y0));
          const r = Math.min(4, h);
          const up = b.value >= 0;
          const path = up
            ? `M${cx - bw / 2},${y0} V${top + r} Q${cx - bw / 2},${top} ${cx - bw / 2 + r},${top} H${cx + bw / 2 - r} Q${cx + bw / 2},${top} ${cx + bw / 2},${top + r} V${y0} Z`
            : `M${cx - bw / 2},${y0} V${y0 + h - r} Q${cx - bw / 2},${y0 + h} ${cx - bw / 2 + r},${y0 + h} H${cx + bw / 2 - r} Q${cx + bw / 2},${y0 + h} ${cx + bw / 2},${y0 + h - r} V${y0} Z`;
          return (
            <g key={i} onMouseEnter={() => setHover(i)}>
              <rect x={cx - slot / 2} y={PAD.t} width={slot} height={H - PAD.t - PAD.b} fill="transparent" />
              <path d={path} fill={color} opacity={b.muted ? 0.45 : hover === null || hover === i ? 1 : 0.6} />
              <text x={cx} y={H - 22} fontSize={10.5} textAnchor="middle" fill="var(--muted)">{b.label}</text>
              {b.sub && <text x={cx} y={H - 9} fontSize={10} textAnchor="middle" fill="var(--muted)" className="num">{b.sub}</text>}
            </g>
          );
        })}
      </svg>
      <div className="text-[12px] text-ink-2 num min-h-[18px] text-right">
        {hover !== null ? `${bars[hover].label}${bars[hover].sub ? " (" + bars[hover].sub + ")" : ""} · ${yFmt(bars[hover].value)}${yUnit}` : ""}
      </div>
    </div>
  );
}
function niceStep(raw: number) { const p = Math.pow(10, Math.floor(Math.log10(raw))); const m = raw / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p; }
